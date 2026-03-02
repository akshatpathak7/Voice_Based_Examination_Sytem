from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import os
import re
import secrets
from datetime import datetime

from models import db, Registration, Exam, Question, Answer, ExamSession, Candidate
from werkzeug.security import check_password_hash, generate_password_hash
from crypto_utils import (
    load_master_key,
    decrypt_exam_key,
    encrypt_answer,
    decrypt_answer,
    compute_integrity_hash,
    verify_integrity_hash,
)

try:
    import language_tool_python
except ImportError:
    language_tool_python = None

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "secretkey123")

# -----  DATABASE PATH -----
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///exam.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# ----- LOAD MASTER ENCRYPTION KEY -----
_master_key = load_master_key()

_grammar_tool = None
if language_tool_python is not None:
    try:
        _grammar_tool = language_tool_python.LanguageTool("en-US")
    except Exception:
        _grammar_tool = None


def normalize_answer(question_text, answer_text):
    text = " ".join(answer_text.strip().split())

    if not text:
        return text

    # Basic fixes for common STT artefacts and casing
    text = re.sub(r"\bim\b", "I'm", text, flags=re.IGNORECASE)
    text = re.sub(r"\bi\b", "I", text)

    # Remove common filler words
    fillers_pattern = r"\b(um+|uh+|erm|like|you know|sort of|kind of)\b"
    text = re.sub(fillers_pattern, "", text, flags=re.IGNORECASE)
    text = " ".join(text.split())

    # Fix a/an usage based on following word
    words = text.split()
    for idx in range(len(words) - 1):
        if words[idx].lower() in ("a", "an"):
            next_word = re.sub(r"[^A-Za-z]", "", words[idx + 1])
            if next_word:
                starts_vowel = next_word[0].lower() in "aeiou"
                if words[idx].lower() == "a" and starts_vowel:
                    words[idx] = "an"
                elif words[idx].lower() == "an" and not starts_vowel:
                    words[idx] = "a"

    text = " ".join(words)

    # Capitalize first character and start of new sentences
    if text:
        text = text[0].upper() + text[1:]
    text = re.sub(r"(?<=[\.\!\?]\s)([a-z])", lambda match: match.group(1).upper(), text)

    # Ensure trailing punctuation
    if text and text[-1] not in ".!?":
        text += "."

    # Simple question-specific rule example
    if question_text and "capital of" in question_text.lower():
        text = text.title()

    # Optional grammar correction step for better contextual correctness
    if _grammar_tool is not None:
        try:
            matches = _grammar_tool.check(text)
            text = language_tool_python.utils.correct(text, matches)
        except Exception:
            # If grammar tool fails for any reason, fall back to rule-based result
            pass

    return text

# ---------- ROUTES ----------

@app.route('/')
def index():
    return render_template('index.html')


# ---------- SHOW LOGIN PAGE ----------
@app.route('/login', methods=['GET'])
def show_login():
    return render_template('login.html')


# ---------- PROCESS LOGIN ----------
@app.route('/login', methods=['POST'])
def login():

    username = request.form['username']
    password = request.form['password']

    user = Registration.query.filter_by(username=username).first()

    if not user:
        flash("Invalid username or password")
        return redirect(url_for('show_login'))

    if not check_password_hash(user.password_hash, password):
        flash("Invalid username or password")
        return redirect(url_for('show_login'))

    token = secrets.token_hex(32)
    user.session_token = token
    db.session.commit()

    session['user_id'] = user.reg_id
    session['role'] = user.role
    session['session_token'] = token

    if user.role == 'INVIGILATOR':
        return redirect(url_for('invigilator_dashboard'))

    elif user.role == 'CANDIDATE':
        return redirect(url_for('candidate_dashboard'))

    elif user.role == 'ADMIN':
        return redirect(url_for('admin_dashboard'))

    return redirect(url_for('index'))


# ---------- SESSION GUARD ----------

def verify_session():
    """Return True if the current Flask session token matches the DB.

    When another device logs in with the same credentials, the DB token
    is replaced, invalidating all previous sessions for that user.
    """
    uid = session.get('user_id')
    token = session.get('session_token')
    if not uid or not token:
        return False
    user = Registration.query.get(uid)
    if not user:
        return False
    return user.session_token == token


# ---------- DASHBOARDS ----------

@app.route('/candidate/dashboard')
def candidate_dashboard():

    if 'user_id' not in session or session.get('role') != 'CANDIDATE':
        return redirect(url_for('show_login'))

    if not verify_session():
        session.clear()
        flash("Your session has been ended because this account was logged in on another device.")
        return redirect(url_for('show_login'))

    return render_template('student_dashboard.html')


@app.route('/admin/dashboard')
def admin_dashboard():

    if 'user_id' not in session or session.get('role') != 'ADMIN':
        return redirect(url_for('show_login'))

    return render_template('admin_dashboard.html')


# ---------- CREATE STUDENT ACCOUNT ----------

@app.route('/invigilator/create_student', methods=['POST'])
def create_student():
    allowed_roles = ('INVIGILATOR', 'ADMIN')
    if session.get('role') not in allowed_roles:
        return jsonify({"error": "unauthorized"}), 401

    full_name = request.form.get('full_name', '').strip()
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    phone = request.form.get('phone_no', '').strip()
    registration_no = request.form.get('registration_no', '').strip()

    if not all([full_name, username, email, password, registration_no]):
        flash("All required fields must be filled.")
        return redirect(request.referrer or url_for('invigilator_dashboard'))

    if Registration.query.filter_by(username=username).first():
        flash(f"Username '{username}' already exists.")
        return redirect(request.referrer or url_for('invigilator_dashboard'))

    if Registration.query.filter_by(email=email).first():
        flash(f"Email '{email}' already exists.")
        return redirect(request.referrer or url_for('invigilator_dashboard'))

    if Candidate.query.filter_by(registration_no=registration_no).first():
        flash(f"Registration number '{registration_no}' already exists.")
        return redirect(request.referrer or url_for('invigilator_dashboard'))

    reg = Registration(
        full_name=full_name,
        username=username,
        email=email,
        password_hash=generate_password_hash(password),
        role='CANDIDATE',
        phone_no=phone or None,
    )
    db.session.add(reg)
    db.session.flush()

    candidate = Candidate(
        reg_id=reg.reg_id,
        registration_no=registration_no,
    )
    db.session.add(candidate)
    db.session.commit()

    flash(f"Student '{full_name}' created successfully (username: {username}).")
    return redirect(request.referrer or url_for('invigilator_dashboard'))


# ---------- INVIGILATOR DASHBOARD (SINGLE PAGE) ----------

@app.route('/invigilator/dashboard')
def invigilator_dashboard():

    if session.get('role') != 'INVIGILATOR':
        return redirect(url_for('show_login'))

    exams = Exam.query.all()
    sessions = ExamSession.query.all()

    return render_template(
        'invigilator_dashboard.html',
        exams=exams,
        sessions=sessions
    )


# ---------- QUESTION CRUD APIS ----------

@app.route('/invigilator/get_questions/<int:exam_id>')
def get_exam_questions(exam_id):

    if session.get('role') != 'INVIGILATOR':
        return jsonify({"error": "unauthorized"}), 401

    questions = Question.query.filter_by(exam_id=exam_id).all()

    data = []

    for q in questions:
        data.append({
            "id": q.question_id,
            "text": q.question_text
        })

    return jsonify(data)


@app.route('/invigilator/add_question', methods=['POST'])
def add_question():

    if session.get('role') != 'INVIGILATOR':
        return jsonify({"error": "unauthorized"}), 401

    exam_id = request.form['exam_id']
    text = request.form['text']

    q = Question(exam_id=exam_id, question_text=text)

    db.session.add(q)
    db.session.commit()

    return jsonify({"status": "added"})


@app.route('/invigilator/update_question', methods=['POST'])
def update_question():

    if session.get('role') != 'INVIGILATOR':
        return jsonify({"error": "unauthorized"}), 401

    qid = request.form['qid']
    text = request.form['text']

    q = Question.query.get(qid)
    q.question_text = text

    db.session.commit()

    return jsonify({"status": "updated"})


@app.route('/invigilator/delete_question/<int:qid>')
def delete_question(qid):

    if session.get('role') != 'INVIGILATOR':
        return jsonify({"error": "unauthorized"}), 401

    q = Question.query.get(qid)

    db.session.delete(q)
    db.session.commit()

    return jsonify({"status": "deleted"})


# ---------- MARKS MODULE ----------

@app.route('/invigilator/save_marks', methods=['POST'])
def save_marks():

    if session.get('role') != 'INVIGILATOR':
        return jsonify({"error": "unauthorized"}), 401

    answer_id = request.form['answer_id']
    marks = request.form['marks']

    ans = Answer.query.get(answer_id)

    ans.marks = marks

    db.session.commit()

    return jsonify({"status": "marks saved"})


@app.route('/invigilator/get_answers/<int:session_id>')
def get_answers(session_id):

    if session.get('role') != 'INVIGILATOR':
        return jsonify({"error": "unauthorized"}), 401

    exam_session = ExamSession.query.get(session_id)
    if not exam_session:
        return jsonify({"error": "session not found"}), 404

    exam = Exam.query.get(exam_session.exam_id)
    exam_key = decrypt_exam_key(
        exam.enc_key_ciphertext, exam.enc_key_iv, exam.enc_key_tag, _master_key
    )

    answers = Answer.query.filter_by(session_id=session_id).all()
    data = []

    for a in answers:
        q = Question.query.get(a.question_id)

        try:
            plaintext = decrypt_answer(
                a.answer_ciphertext, a.answer_iv, a.answer_tag, exam_key
            )
            tampered = not verify_integrity_hash(
                _master_key, plaintext, a.question_id,
                session_id, a.encrypted_at, a.integrity_hash
            )
        except Exception:
            plaintext = "[DECRYPTION FAILED — answer may have been tampered with]"
            tampered = True

        data.append({
            "answer_id": a.answer_id,
            "question": q.question_text if q else "Unknown",
            "answer": plaintext,
            "marks": a.marks,
            "tampered": tampered,
        })

    return jsonify(data)


@app.route('/invigilator/get_result/<int:session_id>')
def get_result(session_id):

    if session.get('role') != 'INVIGILATOR':
        return jsonify({"error": "unauthorized"}), 401

    answers = Answer.query.filter_by(session_id=session_id).all()

    total = 0

    for a in answers:
        total += a.marks or 0

    return jsonify({"total_marks": total})


# ---------- STUDENT EXAM APIS ----------

@app.route('/api/questions')
def get_questions():

    if 'user_id' not in session:
        return jsonify({"error": "not logged in"}), 401

    if not verify_session():
        session.clear()
        return jsonify({"error": "session_expired"}), 401

    exam = Exam.query.first()

    questions = Question.query.filter_by(exam_id=exam.exam_id).all()

    data = []
    for q in questions:
        data.append({
            "id": q.question_id,
            "text": q.question_text
        })

    return jsonify(data)


@app.route('/api/save_answer', methods=['POST'])
def save_answer():

    if 'exam_session_id' not in session:
        return jsonify({"error": "session not started"}), 400

    if not verify_session():
        session.clear()
        return jsonify({"error": "session_expired"}), 401

    data = request.get_json()
    question_id = data['question_id']
    session_id = session['exam_session_id']

    question = Question.query.get(question_id)
    normalized_answer = normalize_answer(
        question.question_text if question else "",
        data['answer']
    )

    # --- Retrieve the per-exam encryption key ---
    exam_session = ExamSession.query.get(session_id)
    exam = Exam.query.get(exam_session.exam_id)
    exam_key = decrypt_exam_key(
        exam.enc_key_ciphertext, exam.enc_key_iv, exam.enc_key_tag, _master_key
    )

    # --- Encrypt the normalised answer ---
    ciphertext, iv, tag = encrypt_answer(normalized_answer, exam_key)
    now = datetime.utcnow()
    integrity = compute_integrity_hash(
        _master_key, normalized_answer, question_id, session_id, now
    )

    answer = Answer(
        session_id=session_id,
        question_id=question_id,
        answer_ciphertext=ciphertext,
        answer_iv=iv,
        answer_tag=tag,
        integrity_hash=integrity,
        encrypted_at=now,
    )

    db.session.add(answer)
    db.session.commit()

    return jsonify({
        "status": "saved",
        "normalized_answer": normalized_answer
    })


@app.route('/api/start_exam')
def start_exam():

    if 'user_id' not in session:
        return jsonify({"error": "not logged in"}), 401

    if not verify_session():
        session.clear()
        return jsonify({"error": "session_expired"}), 401

    user_id = session['user_id']

    candidate = Candidate.query.filter_by(reg_id=user_id).first()

    if not candidate:
        return jsonify({"error": "Candidate profile not found for this user"}), 400

    exam = Exam.query.first()

    if not exam:
        return jsonify({"error": "No exam available"}), 400

    new_session = ExamSession(
        exam_id=exam.exam_id,
        candidate_id=candidate.candidate_id
    )

    db.session.add(new_session)
    db.session.commit()

    session['exam_session_id'] = new_session.session_id

    return jsonify({
        "session_id": new_session.session_id,
        "duration_minutes": exam.duration,
    })


# ---------- EXAM SUBMITTED ----------
@app.route('/exam/submitted')
def exam_submitted():
    return render_template('exam_submitted.html')


# ---------- LOGOUT ----------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


# ---------- RUN APPLICATION ----------
if __name__ == '__main__':
    app.run(debug=True)
