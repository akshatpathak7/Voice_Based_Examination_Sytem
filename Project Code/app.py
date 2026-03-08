from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, g
import math
import os
import re
import secrets
from datetime import datetime, timezone

from models import init_app as init_db, get_db, get_next_id
from werkzeug.security import check_password_hash, generate_password_hash
from crypto_utils import (
    load_master_key,
    generate_exam_key,
    encrypt_exam_key,
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

# ----- DATABASE -----
app.config["MONGO_URI"] = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
app.config["MONGO_DB_NAME"] = os.environ.get("MONGO_DB_NAME", "exam_db")

init_db(app)

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

    text = re.sub(r"\bim\b", "I'm", text, flags=re.IGNORECASE)
    text = re.sub(r"\bi\b", "I", text)

    fillers_pattern = r"\b(um+|uh+|erm|like|you know|sort of|kind of)\b"
    text = re.sub(fillers_pattern, "", text, flags=re.IGNORECASE)
    text = " ".join(text.split())

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

    if text:
        text = text[0].upper() + text[1:]
    text = re.sub(r"(?<=[\.\!\?]\s)([a-z])", lambda m: m.group(1).upper(), text)

    if text and text[-1] not in ".!?":
        text += "."

    if question_text and "capital of" in question_text.lower():
        text = text.title()

    if _grammar_tool is not None:
        try:
            matches = _grammar_tool.check(text)
            text = language_tool_python.utils.correct(text, matches)
        except Exception:
            pass

    return text


# ---------- ROUTES ----------

@app.route('/')
def index():
    return render_template('index.html')


# ---------- SHOW LOGIN PAGE ----------
@app.route('/login', methods=['GET'])
def show_login():
    # If any role is already logged in, we don't redirect (user may want to log in as another role in another tab).
    return render_template('login.html')


# ---------- PROCESS LOGIN ----------
@app.route('/login', methods=['POST'])
def login():
    db = get_db()
    username = request.form['username']
    password = request.form['password']

    user = db.users.find_one({"username": username})

    if not user:
        flash("Invalid username or password")
        return redirect(url_for('show_login'))

    if not check_password_hash(user["password_hash"], password):
        flash("Invalid username or password")
        return redirect(url_for('show_login'))

    role = user["role"]
    accounts = session.get("accounts") or {}
    existing = accounts.get(role)

    # Only block when it's the SAME user (same user_id): same login, same role, valid session.
    # Different user (different ID) same role => allow login and replace the account.
    def _same_user_id(account, u):
        if not account or not u:
            return False
        eid, uid = account.get("user_id"), u.get("_id")
        if eid is None or uid is None:
            return False
        try:
            return int(eid) == int(uid)
        except (TypeError, ValueError):
            return False

    if (
        existing is not None
        and _same_user_id(existing, user)
        and verify_session_for_role(role, existing)
    ):
        flash("You are already logged in as this user. Use your other tab or go to dashboard.", "already_logged_in")
        return redirect(url_for("show_login"))

    # New or replacing session: issue new token (invalidates any other device/tab with old token)
    token = secrets.token_hex(32)
    db.users.update_one({"_id": user["_id"]}, {"$set": {"session_token": token}})

    accounts[role] = {"user_id": user["_id"], "session_token": token}
    if role == "CANDIDATE":
        accounts[role]["exam_session_id"] = None  # set when they start exam
    session["accounts"] = accounts

    if role == 'INVIGILATOR':
        return redirect(url_for('invigilator_dashboard'))

    elif user["role"] == 'CANDIDATE':
        return redirect(url_for('candidate_dashboard'))

    elif user["role"] == 'ADMIN':
        return redirect(url_for('admin_dashboard'))

    elif user["role"] == 'EXAMINER':
        return redirect(url_for('examiner_dashboard'))

    return redirect(url_for('index'))


@app.route('/go')
def go_to_dashboard():
    """If user has a valid session for any role, redirect to that dashboard. Else index."""
    accounts = session.get("accounts") or {}
    for role in ("ADMIN", "INVIGILATOR", "EXAMINER", "CANDIDATE"):
        acc = accounts.get(role)
        if acc and verify_session_for_role(role, acc):
            if role == "INVIGILATOR":
                return redirect(url_for("invigilator_dashboard"))
            if role == "CANDIDATE":
                return redirect(url_for("candidate_dashboard"))
            if role == "ADMIN":
                return redirect(url_for("admin_dashboard"))
            if role == "EXAMINER":
                return redirect(url_for("examiner_dashboard"))
    return redirect(url_for("index"))


# ---------- SESSION GUARD (multi-account: one login per role in same browser) ----------

def get_request_role():
    """Return the role required for this path, or None for public routes."""
    path = request.path
    if path in ("/", "/login", "/logout", "/exam/submitted", "/go") or path.startswith("/static/"):
        return None
    if path.startswith("/candidate"):
        return "CANDIDATE"
    if path.startswith("/admin"):
        return "ADMIN"
    if path.startswith("/invigilator"):
        return "INVIGILATOR"
    if path.startswith("/examiner"):
        return "EXAMINER"
    if path.startswith("/api/"):
        return "CANDIDATE"
    return None


def verify_session_for_role(role, account):
    """Return True if this account's token matches the DB (single session per user per role)."""
    if not account:
        return False
    uid = account.get("user_id")
    token = account.get("session_token")
    if not uid or not token:
        return False
    db = get_db()
    user = db.users.find_one({"_id": uid})
    if not user:
        return False
    return user.get("session_token") == token


@app.before_request
def enforce_single_session():
    """Validate the session for the current request's role. One login per user per role;
    different roles (e.g. student + invigilator) can be logged in in different tabs.
    """
    role = get_request_role()
    if role is None:
        return None

    accounts = session.get("accounts") or {}
    account = accounts.get(role)
    if account is None:
        if request.path.startswith("/api/") or "application/json" in request.headers.get("Accept", ""):
            return jsonify({"error": "session_expired"}), 401
        return redirect(url_for("show_login"))

    if not verify_session_for_role(role, account):
        accounts.pop(role, None)
        session["accounts"] = accounts
        flash("Your session has been ended because this account was logged in on another device.")
        if request.path.startswith("/api/") or "application/json" in request.headers.get("Accept", ""):
            return jsonify({"error": "session_expired"}), 401
        return redirect(url_for("show_login"))

    g.current_user_id = account["user_id"]
    g.current_role = role
    g.exam_session_id = account.get("exam_session_id") if role == "CANDIDATE" else None


# ---------- DASHBOARDS ----------

@app.route('/candidate/dashboard')
def candidate_dashboard():
    db = get_db()
    if g.current_role != 'CANDIDATE':
        return redirect(url_for('show_login'))

    # Check if invigilator already started the exam for this student (they have a pending session)
    candidate = db.candidates.find_one({"reg_id": g.current_user_id})
    exam = _get_active_exam(db)
    invigilator_started = False
    if candidate and exam:
        invigilator_started = db.exam_sessions.find_one({
            "candidate_id": candidate["_id"],
            "exam_id": exam["_id"],
            "status": {"$ne": "SUBMITTED"},
        }) is not None

    return render_template(
        'student_dashboard.html',
        invigilator_started=invigilator_started,
    )


@app.route('/admin/dashboard')
def admin_dashboard():

    if g.current_role != 'ADMIN':
        return redirect(url_for('show_login'))

    db = get_db()

    users = list(db.users.find())
    exams = list(db.exams.find())
    candidates = list(db.candidates.find())

    # Enrich examiner assignments with names
    examiner_assignments = []
    for a in db.examiner_assignments.find():
        examiner = db.users.find_one({"_id": a["examiner_id"]})
        candidate = db.candidates.find_one({"_id": a["candidate_id"]})
        student_user = db.users.find_one({"_id": candidate["reg_id"]}) if candidate else None
        exam = db.exams.find_one({"_id": a["exam_id"]})
        examiner_assignments.append({
            "_id": a["_id"],
            "examiner_name": examiner["full_name"] if examiner else "Unknown",
            "student_name": student_user["full_name"] if student_user else "Unknown",
            "registration_no": candidate.get("registration_no", "N/A") if candidate else "N/A",
            "exam_name": exam["exam_name"] if exam else "Unknown",
        })

    # Invigilator assignments (exams created_by)
    invigilator_assignments = []
    for exam in exams:
        inv = db.users.find_one({"_id": exam.get("created_by")})
        if inv:
            invigilator_assignments.append({
                "exam_id": exam["_id"],
                "invigilator_name": inv["full_name"],
                "exam_name": exam["exam_name"],
            })

    return render_template(
        'admin_dashboard.html',
        users=users,
        exams=exams,
        candidates=candidates,
        examiner_assignments=examiner_assignments,
        invigilator_assignments=invigilator_assignments,
    )


# ---------- ADMIN: CREATE USER ----------

@app.route('/admin/create_user', methods=['POST'])
def admin_create_user():
    db = get_db()

    if g.current_role != 'ADMIN':
        return redirect(url_for('show_login'))

    full_name = request.form.get('full_name', '').strip()
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    phone = request.form.get('phone_no', '').strip()
    role = request.form.get('role', '').strip()
    registration_no = request.form.get('registration_no', '').strip()

    if role not in ('INVIGILATOR', 'EXAMINER', 'CANDIDATE', 'ADMIN'):
        flash("Invalid role selected.")
        return redirect(url_for('admin_dashboard'))

    if not all([full_name, username, email, password]):
        flash("All required fields must be filled.")
        return redirect(url_for('admin_dashboard'))

    if role == 'CANDIDATE' and not registration_no:
        flash("Registration number is required for students.")
        return redirect(url_for('admin_dashboard'))

    if db.users.find_one({"username": username}):
        flash(f"Username '{username}' already exists.")
        return redirect(url_for('admin_dashboard'))

    if db.users.find_one({"email": email}):
        flash(f"Email '{email}' already exists.")
        return redirect(url_for('admin_dashboard'))

    if role == 'CANDIDATE' and db.candidates.find_one({"registration_no": registration_no}):
        flash(f"Registration number '{registration_no}' already exists.")
        return redirect(url_for('admin_dashboard'))

    user_id = get_next_id("users")
    db.users.insert_one({
        "_id": user_id,
        "full_name": full_name,
        "username": username,
        "email": email,
        "password_hash": generate_password_hash(password),
        "role": role,
        "phone_no": phone or None,
        "created_at": datetime.now(timezone.utc),
        "session_token": None,
    })

    if role == 'CANDIDATE':
        cand_id = get_next_id("candidates")
        db.candidates.insert_one({
            "_id": cand_id,
            "reg_id": user_id,
            "registration_no": registration_no,
        })

    flash(f"{role.title()} '{full_name}' created successfully (username: {username}).")
    return redirect(url_for('admin_dashboard'))


# ---------- ADMIN: DELETE STUDENT ----------

@app.route('/admin/delete_student/<int:user_id>', methods=['POST'])
def admin_delete_student(user_id):
    db = get_db()

    if g.current_role != 'ADMIN':
        return redirect(url_for('show_login'))

    user = db.users.find_one({"_id": user_id})
    if not user or user["role"] != 'CANDIDATE':
        flash("Student not found.")
        return redirect(url_for('admin_dashboard'))

    # Cascade: candidate profile, assignments, sessions, answers
    candidate = db.candidates.find_one({"reg_id": user_id})
    if candidate:
        # Remove examiner assignments for this candidate
        db.examiner_assignments.delete_many({"candidate_id": candidate["_id"]})
        # Remove exam sessions and their answers
        sessions = list(db.exam_sessions.find({"candidate_id": candidate["_id"]}))
        for sess in sessions:
            db.answers.delete_many({"session_id": sess["_id"]})
        db.exam_sessions.delete_many({"candidate_id": candidate["_id"]})
        # Remove candidate profile
        db.candidates.delete_one({"_id": candidate["_id"]})

    db.users.delete_one({"_id": user_id})
    flash(f"Student '{user['full_name']}' deleted successfully.")
    return redirect(url_for('admin_dashboard'))


# ---------- ADMIN: ASSIGN EXAMINER TO STUDENT ----------

@app.route('/admin/assign_examiner', methods=['POST'])
def admin_assign_examiner():
    db = get_db()

    if g.current_role != 'ADMIN':
        return redirect(url_for('show_login'))

    examiner_id = int(request.form['examiner_id'])
    candidate_id = int(request.form['candidate_id'])
    exam_id = int(request.form['exam_id'])

    # Check if assignment already exists
    existing = db.examiner_assignments.find_one({
        "examiner_id": examiner_id,
        "candidate_id": candidate_id,
        "exam_id": exam_id,
    })
    if existing:
        flash("This assignment already exists.")
        return redirect(url_for('admin_dashboard'))

    assign_id = get_next_id("examiner_assignments")
    db.examiner_assignments.insert_one({
        "_id": assign_id,
        "examiner_id": examiner_id,
        "candidate_id": candidate_id,
        "exam_id": exam_id,
    })

    flash("Examiner assigned to student successfully.")
    return redirect(url_for('admin_dashboard'))


# ---------- ADMIN: REMOVE EXAMINER ASSIGNMENT ----------

@app.route('/admin/remove_examiner_assignment/<int:assign_id>', methods=['POST'])
def admin_remove_examiner_assignment(assign_id):
    db = get_db()

    if g.current_role != 'ADMIN':
        return redirect(url_for('show_login'))

    db.examiner_assignments.delete_one({"_id": assign_id})
    flash("Examiner assignment removed.")
    return redirect(url_for('admin_dashboard'))


# ---------- ADMIN: ASSIGN INVIGILATOR TO EXAM ----------

@app.route('/admin/assign_invigilator', methods=['POST'])
def admin_assign_invigilator():
    db = get_db()

    if g.current_role != 'ADMIN':
        return redirect(url_for('show_login'))

    invigilator_id = int(request.form['invigilator_id'])
    exam_id = int(request.form['exam_id'])

    # Update the exam's created_by to this invigilator
    db.exams.update_one({"_id": exam_id}, {"$set": {"created_by": invigilator_id}})

    inv = db.users.find_one({"_id": invigilator_id})
    exam = db.exams.find_one({"_id": exam_id})
    flash(f"Invigilator '{inv['full_name']}' assigned to '{exam['exam_name']}'.")
    return redirect(url_for('admin_dashboard'))


# ---------- CREATE STUDENT ACCOUNT ----------

@app.route('/invigilator/create_student', methods=['POST'])
def create_student():
    db = get_db()
    allowed_roles = ('INVIGILATOR', 'ADMIN')
    if g.current_role not in allowed_roles:
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

    if db.users.find_one({"username": username}):
        flash(f"Username '{username}' already exists.")
        return redirect(request.referrer or url_for('invigilator_dashboard'))

    if db.users.find_one({"email": email}):
        flash(f"Email '{email}' already exists.")
        return redirect(request.referrer or url_for('invigilator_dashboard'))

    if db.candidates.find_one({"registration_no": registration_no}):
        flash(f"Registration number '{registration_no}' already exists.")
        return redirect(request.referrer or url_for('invigilator_dashboard'))

    reg_id = get_next_id("users")
    db.users.insert_one({
        "_id": reg_id,
        "full_name": full_name,
        "username": username,
        "email": email,
        "password_hash": generate_password_hash(password),
        "role": "CANDIDATE",
        "phone_no": phone or None,
        "created_at": datetime.now(timezone.utc),
        "session_token": None,
    })

    candidate_id = get_next_id("candidates")
    db.candidates.insert_one({
        "_id": candidate_id,
        "reg_id": reg_id,
        "registration_no": registration_no,
    })

    flash(f"Student '{full_name}' created successfully (username: {username}).")
    return redirect(request.referrer or url_for('invigilator_dashboard'))


# ---------- INVIGILATOR: ASSIGN STUDENT TO EXAM ----------

@app.route('/invigilator/assign_student_exam', methods=['POST'])
def assign_student_exam():
    db = get_db()
    if g.current_role != 'INVIGILATOR':
        return redirect(url_for('show_login'))

    candidate_id = int(request.form.get('candidate_id'))
    exam_id = int(request.form.get('exam_id'))

    existing = db.exam_assignments.find_one({
        "candidate_id": candidate_id,
        "exam_id": exam_id,
    })
    if existing:
        flash("This student is already assigned to that exam.")
        return redirect(url_for('invigilator_dashboard'))

    assign_id = get_next_id("exam_assignments")
    db.exam_assignments.insert_one({
        "_id": assign_id,
        "candidate_id": candidate_id,
        "exam_id": exam_id,
        "assigned_by": g.current_user_id,
    })
    flash("Student assigned to exam.")
    return redirect(url_for('invigilator_dashboard'))


@app.route('/invigilator/unassign_student_exam/<int:assign_id>', methods=['POST'])
def unassign_student_exam(assign_id):
    db = get_db()
    if g.current_role != 'INVIGILATOR':
        return redirect(url_for('show_login'))

    db.exam_assignments.delete_one({"_id": assign_id})
    flash("Student unassigned from exam.")
    return redirect(url_for('invigilator_dashboard'))


# ---------- INVIGILATOR DASHBOARD (SINGLE PAGE) ----------

@app.route('/invigilator/dashboard')
def invigilator_dashboard():

    if g.current_role != 'INVIGILATOR':
        return redirect(url_for('show_login'))

    db = get_db()
    exams = list(db.exams.find())
    sessions = list(db.exam_sessions.find())

    # Candidates (students) for assign-student-to-exam
    candidates = []
    for c in db.candidates.find():
        u = db.users.find_one({"_id": c["reg_id"]})
        candidates.append({
            "_id": c["_id"],
            "full_name": u["full_name"] if u else "Unknown",
            "registration_no": c.get("registration_no", "N/A"),
        })

    # Invigilator-created exam assignments (candidate + exam)
    exam_assignments = []
    for a in db.exam_assignments.find():
        c = db.candidates.find_one({"_id": a["candidate_id"]})
        u = db.users.find_one({"_id": c["reg_id"]}) if c else None
        ex = db.exams.find_one({"_id": a["exam_id"]})
        exam_assignments.append({
            "_id": a["_id"],
            "candidate_name": u["full_name"] if u else "Unknown",
            "exam_name": ex["exam_name"] if ex else "Unknown",
            "candidate_id": a["candidate_id"],
            "exam_id": a["exam_id"],
        })

    return render_template(
        'invigilator_dashboard.html',
        exams=exams,
        sessions=sessions,
        candidates=candidates,
        exam_assignments=exam_assignments,
    )


# ---------- CREATE EXAM ----------

@app.route('/invigilator/create_exam', methods=['POST'])
def create_exam():
    db = get_db()

    if g.current_role not in ('INVIGILATOR', 'ADMIN'):
        return jsonify({"error": "unauthorized"}), 401

    exam_name = request.form.get('name', '').strip()
    duration = request.form.get('duration', '60').strip()

    if not exam_name:
        flash("Exam name is required.")
        return redirect(url_for('invigilator_dashboard'))

    try:
        duration = int(duration)
    except ValueError:
        duration = 60

    # Generate and encrypt a per-exam AES key
    exam_key = generate_exam_key()
    enc_ct, enc_iv, enc_tag = encrypt_exam_key(exam_key, _master_key)

    exam_id = get_next_id("exams")
    db.exams.insert_one({
        "_id": exam_id,
        "exam_name": exam_name,
        "duration": duration,
        "total_marks": 100,
        "created_by": g.current_user_id,
        "enc_key_ciphertext": enc_ct,
        "enc_key_iv": enc_iv,
        "enc_key_tag": enc_tag,
    })

    flash(f"Exam '{exam_name}' created successfully.")
    return redirect(url_for('invigilator_dashboard'))


# ---------- START EXAM (invigilator starts for all assigned students) ----------

def _get_active_exam(db):
    """Return the exam that is currently active (is_active=True), or the first exam."""
    exam = db.exams.find_one({"is_active": True})
    if exam:
        return exam
    return db.exams.find_one()


@app.route('/invigilator/start_exam/<int:exam_id>')
def start_exam_invigilator(exam_id):
    if g.current_role != 'INVIGILATOR':
        return redirect(url_for('show_login'))

    db = get_db()
    exam = db.exams.find_one({"_id": exam_id})
    if not exam:
        flash("Exam not found.")
        return redirect(url_for('invigilator_dashboard'))

    # Set this exam as the only active one; deactivate others
    db.exams.update_many({}, {"$set": {"is_active": False}})
    db.exams.update_one({"_id": exam_id}, {"$set": {"is_active": True}})

    # Candidates assigned via examiner_assignments (admin) or exam_assignments (invigilator)
    candidate_ids = set()
    for a in db.examiner_assignments.find({"exam_id": exam_id}):
        candidate_ids.add(a["candidate_id"])
    for a in db.exam_assignments.find({"exam_id": exam_id}):
        candidate_ids.add(a["candidate_id"])
    candidate_ids = list(candidate_ids)

    created = 0
    for cid in candidate_ids:
        # Only create if they don't already have a non-submitted session for this exam
        existing = db.exam_sessions.find_one({
            "candidate_id": cid,
            "exam_id": exam_id,
            "status": {"$ne": "SUBMITTED"},
        })
        if not existing:
            session_id = get_next_id("exam_sessions")
            db.exam_sessions.insert_one({
                "_id": session_id,
                "exam_id": exam_id,
                "candidate_id": cid,
                "start_time": datetime.now(timezone.utc),
                "end_time": None,
                "status": "STARTED",
            })
            created += 1

    flash(
        f"Exam '{exam['exam_name']}' started. "
        f"Session created for {created} student(s) (total assigned: {len(candidate_ids)})."
    )
    return redirect(url_for('invigilator_dashboard'))


# ---------- QUESTION CRUD APIS ----------

@app.route('/invigilator/get_questions/<int:exam_id>')
def get_exam_questions(exam_id):
    db = get_db()

    if g.current_role != 'INVIGILATOR':
        return jsonify({"error": "unauthorized"}), 401

    questions = list(db.questions.find({"exam_id": exam_id}))

    data = []
    for q in questions:
        data.append({
            "id": q["_id"],
            "text": q["question_text"]
        })

    return jsonify(data)


@app.route('/invigilator/add_question', methods=['POST'])
def add_question():
    db = get_db()

    if g.current_role != 'INVIGILATOR':
        return jsonify({"error": "unauthorized"}), 401

    exam_id = int(request.form['exam_id'])
    text = request.form['text']

    q_id = get_next_id("questions")
    db.questions.insert_one({
        "_id": q_id,
        "exam_id": exam_id,
        "question_text": text,
    })

    return jsonify({"status": "added"})


@app.route('/invigilator/update_question', methods=['POST'])
def update_question():
    db = get_db()

    if g.current_role != 'INVIGILATOR':
        return jsonify({"error": "unauthorized"}), 401

    qid = int(request.form['qid'])
    text = request.form['text']

    db.questions.update_one({"_id": qid}, {"$set": {"question_text": text}})

    return jsonify({"status": "updated"})


@app.route('/invigilator/delete_question/<int:qid>', methods=['POST'])
def delete_question(qid):
    db = get_db()

    if g.current_role != 'INVIGILATOR':
        return jsonify({"error": "unauthorized"}), 401

    db.questions.delete_one({"_id": qid})

    return jsonify({"status": "deleted"})


# ---------- MARKS MODULE ----------

@app.route('/invigilator/save_marks', methods=['POST'])
def save_marks():
    db = get_db()

    if g.current_role != 'INVIGILATOR':
        return jsonify({"error": "unauthorized"}), 401

    answer_id = int(request.form['answer_id'])
    marks = int(request.form['marks'])

    db.answers.update_one({"_id": answer_id}, {"$set": {"marks": marks}})

    return jsonify({"status": "marks saved"})


@app.route('/invigilator/get_answers/<int:session_id>')
def get_answers(session_id):
    db = get_db()

    if g.current_role != 'INVIGILATOR':
        return jsonify({"error": "unauthorized"}), 401

    exam_sess = db.exam_sessions.find_one({"_id": session_id})
    if not exam_sess:
        return jsonify({"error": "session not found"}), 404

    exam = db.exams.find_one({"_id": exam_sess["exam_id"]})
    exam_key = decrypt_exam_key(
        bytes(exam["enc_key_ciphertext"]),
        bytes(exam["enc_key_iv"]),
        bytes(exam["enc_key_tag"]),
        _master_key,
    )

    answers = list(db.answers.find({"session_id": session_id}))
    data = []

    for a in answers:
        q = db.questions.find_one({"_id": a["question_id"]})

        try:
            plaintext = decrypt_answer(
                bytes(a["answer_ciphertext"]),
                bytes(a["answer_iv"]),
                bytes(a["answer_tag"]),
                exam_key,
            )
            tampered = not verify_integrity_hash(
                _master_key, plaintext, a["question_id"],
                session_id, a["encrypted_at"], a["integrity_hash"]
            )
        except Exception:
            plaintext = "[DECRYPTION FAILED — answer may have been tampered with]"
            tampered = True

        data.append({
            "answer_id": a["_id"],
            "question": q["question_text"] if q else "Unknown",
            "answer": plaintext,
            "marks": a.get("marks"),
            "tampered": tampered,
        })

    return jsonify(data)


@app.route('/invigilator/get_result/<int:session_id>')
def get_result(session_id):
    db = get_db()

    if g.current_role != 'INVIGILATOR':
        return jsonify({"error": "unauthorized"}), 401

    answers = list(db.answers.find({"session_id": session_id}))

    total = sum(a.get("marks", 0) or 0 for a in answers)

    return jsonify({"total_marks": total})


# ---------- STUDENT EXAM APIS ----------

@app.route('/api/session_check')
def session_check():
    """Lightweight check for single-session: if session invalid (e.g. logged in elsewhere), before_request returns 401."""
    return jsonify({"ok": True})


@app.route('/api/questions')
def get_questions():
    db = get_db()
    exam = _get_active_exam(db)
    if not exam:
        return jsonify({"error": "No exam available"}), 400

    questions = list(db.questions.find({"exam_id": exam["_id"]}))

    data = []
    for q in questions:
        data.append({
            "id": q["_id"],
            "text": q["question_text"]
        })

    return jsonify(data)


@app.route('/api/save_answer', methods=['POST'])
def save_answer():
    db = get_db()

    if g.exam_session_id is None:
        return jsonify({"error": "session not started"}), 400

    data = request.get_json()
    question_id = data['question_id']
    session_id = g.exam_session_id

    question = db.questions.find_one({"_id": question_id})
    normalized_answer = normalize_answer(
        question["question_text"] if question else "",
        data['answer']
    )

    exam_sess = db.exam_sessions.find_one({"_id": session_id})
    exam = db.exams.find_one({"_id": exam_sess["exam_id"]})
    exam_key = decrypt_exam_key(
        bytes(exam["enc_key_ciphertext"]),
        bytes(exam["enc_key_iv"]),
        bytes(exam["enc_key_tag"]),
        _master_key,
    )

    ciphertext, iv, tag = encrypt_answer(normalized_answer, exam_key)
    now = datetime.now(timezone.utc)
    integrity = compute_integrity_hash(
        _master_key, normalized_answer, question_id, session_id, now
    )

    answer_id = get_next_id("answers")
    db.answers.insert_one({
        "_id": answer_id,
        "session_id": session_id,
        "question_id": question_id,
        "answer_ciphertext": ciphertext,
        "answer_iv": iv,
        "answer_tag": tag,
        "integrity_hash": integrity,
        "encrypted_at": now,
        "marks": None,
    })

    return jsonify({
        "status": "saved",
        "normalized_answer": normalized_answer
    })


@app.route('/api/exam_status')
def exam_status():
    """Return whether invigilator has started an exam for this student (so student UI can poll and auto-start)."""
    db = get_db()
    candidate = db.candidates.find_one({"reg_id": g.current_user_id})
    if not candidate:
        return jsonify({"invigilator_started": False})
    exam = _get_active_exam(db)
    if not exam:
        return jsonify({"invigilator_started": False})
    has_session = db.exam_sessions.find_one({
        "candidate_id": candidate["_id"],
        "exam_id": exam["_id"],
        "status": {"$ne": "SUBMITTED"},
    }) is not None
    return jsonify({"invigilator_started": has_session})


@app.route('/api/start_exam')
def start_exam():
    db = get_db()
    user_id = g.current_user_id
    candidate = db.candidates.find_one({"reg_id": user_id})

    if not candidate:
        return jsonify({"error": "Candidate profile not found for this user"}), 400

    exam = _get_active_exam(db)
    if not exam:
        return jsonify({"error": "No exam available"}), 400

    # Student can start ONLY if invigilator already started the exam for them (session exists).
    # Flow: invigilator assigns student to exam → invigilator starts exam → then student can start.
    existing = db.exam_sessions.find_one({
        "candidate_id": candidate["_id"],
        "exam_id": exam["_id"],
        "status": {"$ne": "SUBMITTED"},
    })
    if not existing:
        return jsonify({
            "error": "You cannot start the exam yet. The invigilator must assign you to an exam and then start it. Wait for the invigilator to start the exam.",
        }), 403

    session.setdefault("accounts", {}).setdefault("CANDIDATE", {})["exam_session_id"] = existing["_id"]
    return jsonify({
        "session_id": existing["_id"],
        "duration_minutes": exam["duration"],
        "invigilator_started": True,
    })


# ---------- EXAM SUBMITTED ----------
@app.route('/exam/submitted')
def exam_submitted():
    return render_template('exam_submitted.html')


# ---------- EXAMINER DASHBOARD ----------

def _examiner_can_access_session(db, examiner_id, session_id):
    """Return True iff the examiner is assigned to the candidate for this session."""
    exam_sess = db.exam_sessions.find_one({"_id": session_id})
    if not exam_sess:
        return False
    assignment = db.examiner_assignments.find_one({
        "examiner_id": examiner_id,
        "candidate_id": exam_sess["candidate_id"],
        "exam_id": exam_sess["exam_id"],
    })
    return assignment is not None


@app.route('/examiner/dashboard')
def examiner_dashboard():
    if g.current_role != 'EXAMINER':
        return redirect(url_for('show_login'))

    db = get_db()
    examiner_id = g.current_user_id

    # Get all assignments for this examiner
    assignments = list(db.examiner_assignments.find({"examiner_id": examiner_id}))

    students = []
    for a in assignments:
        candidate = db.candidates.find_one({"_id": a["candidate_id"]})
        if not candidate:
            continue
        user = db.users.find_one({"_id": candidate["reg_id"]})
        exam = db.exams.find_one({"_id": a["exam_id"]})

        # Find exam sessions for this candidate + exam
        sessions_list = list(db.exam_sessions.find({
            "candidate_id": candidate["_id"],
            "exam_id": a["exam_id"],
        }))

        students.append({
            "candidate_id": candidate["_id"],
            "registration_no": candidate.get("registration_no", "N/A"),
            "full_name": user["full_name"] if user else "Unknown",
            "exam_name": exam["exam_name"] if exam else "Unknown",
            "exam_id": a["exam_id"],
            "sessions": sessions_list,
        })

    return render_template('examiner_dashboard.html', students=students)


@app.route('/examiner/get_student_answers/<int:session_id>')
def get_student_answers(session_id):
    db = get_db()

    if g.current_role != 'EXAMINER':
        return jsonify({"error": "unauthorized"}), 401

    if not _examiner_can_access_session(db, g.current_user_id, session_id):
        return jsonify({"error": "you are not assigned to grade this student's exam"}), 403

    exam_sess = db.exam_sessions.find_one({"_id": session_id})
    if not exam_sess:
        return jsonify({"error": "session not found"}), 404

    exam = db.exams.find_one({"_id": exam_sess["exam_id"]})
    exam_key = decrypt_exam_key(
        bytes(exam["enc_key_ciphertext"]),
        bytes(exam["enc_key_iv"]),
        bytes(exam["enc_key_tag"]),
        _master_key,
    )

    answers = list(db.answers.find({"session_id": session_id}))
    data = []

    for a in answers:
        q = db.questions.find_one({"_id": a["question_id"]})

        try:
            plaintext = decrypt_answer(
                bytes(a["answer_ciphertext"]),
                bytes(a["answer_iv"]),
                bytes(a["answer_tag"]),
                exam_key,
            )
            tampered = not verify_integrity_hash(
                _master_key, plaintext, a["question_id"],
                session_id, a["encrypted_at"], a["integrity_hash"]
            )
        except Exception:
            plaintext = "[DECRYPTION FAILED — answer may have been tampered with]"
            tampered = True

        data.append({
            "answer_id": a["_id"],
            "question": q["question_text"] if q else "Unknown",
            "answer": plaintext,
            "marks": a.get("marks"),
            "ai_marks": a.get("ai_marks"),
            "grading_method": a.get("grading_method"),
            "tampered": tampered,
        })

    return jsonify(data)


@app.route('/examiner/save_grade', methods=['POST'])
def examiner_save_grade():
    db = get_db()

    if g.current_role != 'EXAMINER':
        return jsonify({"error": "unauthorized"}), 401

    answer_id = int(request.form['answer_id'])
    marks = int(request.form['marks'])

    answer_doc = db.answers.find_one({"_id": answer_id})
    if not answer_doc:
        return jsonify({"error": "answer not found"}), 404
    if not _examiner_can_access_session(db, g.current_user_id, answer_doc["session_id"]):
        return jsonify({"error": "you are not assigned to grade this student's exam"}), 403

    db.answers.update_one(
        {"_id": answer_id},
        {"$set": {"marks": marks, "grading_method": "MANUAL"}}
    )

    return jsonify({"status": "marks saved", "marks": marks})


def _ai_score_answer(question_text, answer_text):
    """Heuristic AI grading: scores an answer out of 10.

    Criteria:
      - Length adequacy  (0-4 pts): word count vs 50-word target
      - Keyword match    (0-4 pts): how many question keywords appear in answer
      - Structure        (0-2 pts): multiple sentences with proper punctuation
    """
    if not answer_text or not answer_text.strip():
        return 0

    words = answer_text.split()
    word_count = len(words)

    # --- Length score (0-4) ---
    length_score = min(4, math.ceil((word_count / 50) * 4))

    # --- Keyword relevance (0-4) ---
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "of", "in", "to",
        "and", "or", "for", "with", "on", "at", "by", "from", "it", "its",
        "this", "that", "be", "have", "has", "had", "do", "does", "did",
        "what", "which", "who", "how", "when", "where", "why", "each",
        "every", "all", "any", "give", "state", "explain", "describe",
        "define", "illustrate", "example", "suitable", "real", "world",
        "one", "two", "three", "using", "between", "them", "type",
    }
    q_words = set(w.lower().strip(".,!?;:") for w in question_text.split())
    q_keywords = q_words - stop_words
    q_keywords = {w for w in q_keywords if len(w) > 2}

    if q_keywords:
        answer_lower = answer_text.lower()
        matched = sum(1 for kw in q_keywords if kw in answer_lower)
        keyword_ratio = matched / len(q_keywords)
        keyword_score = min(4, round(keyword_ratio * 4))
    else:
        keyword_score = 2  # neutral if no keywords extracted

    # --- Structure score (0-2) ---
    sentences = [s.strip() for s in re.split(r'[.!?]+', answer_text) if s.strip()]
    if len(sentences) >= 3:
        structure_score = 2
    elif len(sentences) >= 2:
        structure_score = 1
    else:
        structure_score = 0

    total = length_score + keyword_score + structure_score
    return min(10, total)


@app.route('/examiner/ai_grade', methods=['POST'])
def examiner_ai_grade():
    db = get_db()

    if g.current_role != 'EXAMINER':
        return jsonify({"error": "unauthorized"}), 401

    answer_id = int(request.form['answer_id'])
    answer_doc = db.answers.find_one({"_id": answer_id})

    if not answer_doc:
        return jsonify({"error": "answer not found"}), 404
    if not _examiner_can_access_session(db, g.current_user_id, answer_doc["session_id"]):
        return jsonify({"error": "you are not assigned to grade this student's exam"}), 403

    # Decrypt the answer to score it
    exam_sess = db.exam_sessions.find_one({"_id": answer_doc["session_id"]})
    exam = db.exams.find_one({"_id": exam_sess["exam_id"]})
    exam_key = decrypt_exam_key(
        bytes(exam["enc_key_ciphertext"]),
        bytes(exam["enc_key_iv"]),
        bytes(exam["enc_key_tag"]),
        _master_key,
    )

    try:
        plaintext = decrypt_answer(
            bytes(answer_doc["answer_ciphertext"]),
            bytes(answer_doc["answer_iv"]),
            bytes(answer_doc["answer_tag"]),
            exam_key,
        )
    except Exception:
        return jsonify({"error": "decryption failed"}), 500

    question = db.questions.find_one({"_id": answer_doc["question_id"]})
    question_text = question["question_text"] if question else ""

    ai_marks = _ai_score_answer(question_text, plaintext)

    db.answers.update_one(
        {"_id": answer_id},
        {"$set": {"marks": ai_marks, "ai_marks": ai_marks, "grading_method": "AI"}}
    )

    return jsonify({"status": "ai graded", "marks": ai_marks})


@app.route('/examiner/get_result/<int:session_id>')
def examiner_get_result(session_id):
    db = get_db()

    if g.current_role != 'EXAMINER':
        return jsonify({"error": "unauthorized"}), 401

    if not _examiner_can_access_session(db, g.current_user_id, session_id):
        return jsonify({"error": "you are not assigned to grade this student's exam"}), 403

    answers = list(db.answers.find({"session_id": session_id}))
    total = sum(a.get("marks", 0) or 0 for a in answers)

    return jsonify({"total_marks": total})


# ---------- LOGOUT ----------
def _logout_current_role():
    """Remove only the current role from session so other tabs (other roles) stay logged in."""
    accounts = session.get("accounts") or {}
    if g.current_role:
        accounts.pop(g.current_role, None)
        session["accounts"] = accounts
    return redirect(url_for('index'))


@app.route('/candidate/logout')
def candidate_logout():
    return _logout_current_role()


@app.route('/invigilator/logout')
def invigilator_logout():
    return _logout_current_role()


@app.route('/admin/logout')
def admin_logout():
    return _logout_current_role()


@app.route('/examiner/logout')
def examiner_logout():
    return _logout_current_role()


@app.route('/logout')
def logout():
    """Legacy: clear entire session (e.g. from exam_submitted or unknown context)."""
    session.clear()
    return redirect(url_for('index'))


# ---------- RUN APPLICATION ----------
if __name__ == '__main__':
    app.run(debug=True, port=5002)
