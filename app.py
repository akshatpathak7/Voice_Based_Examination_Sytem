from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from models import init_app, get_db, get_next_id
import re

app = Flask(__name__)
app.secret_key = "secretkey123"

# MongoDB config
app.config["MONGO_URI"] = "mongodb://localhost:27017/"
app.config["MONGO_DB_NAME"] = "voice_exam_system"

init_app(app)
db = get_db()


# =========================================================
# INDEX
# =========================================================

@app.route('/')
def index():
    return render_template("index.html")


# =========================================================
# LOGIN
# =========================================================

@app.route('/login', methods=["GET"])
def show_login():
    return render_template("login.html")


@app.route('/login', methods=["POST"])
def login():

    username = request.form["username"]
    password = request.form["password"]

    user = db.users.find_one({"username": username})

    if not user:
        flash("Invalid credentials")
        return redirect(url_for("show_login"))

    if not check_password_hash(user["password_hash"], password):
        flash("Invalid credentials")
        return redirect(url_for("show_login"))

    # FIX: convert ObjectId to string
    session["user_id"] = str(user["_id"])
    session["role"] = user["role"]

    if user["role"] == "ADMIN":
        return redirect("/admin/dashboard")

    if user["role"] == "INVIGILATOR":
        return redirect("/invigilator/dashboard")

    if user["role"] == "CANDIDATE":
        return redirect("/student/dashboard")


# =========================================================
# LOGOUT
# =========================================================

@app.route('/logout')
def logout():
    session.clear()
    return redirect("/")


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route('/admin/dashboard')
def admin_dashboard():

    if session.get("role") != "ADMIN":
        return redirect("/login")

    students = list(db.users.find({"role": "CANDIDATE"}))
    invigilators = list(db.users.find({"role": "INVIGILATOR"}))
    exams = list(db.exams.find())

    return render_template(
        "admin_dashboard.html",
        students=students,
        invigilators=invigilators,
        exams=exams
    )


# =========================================================
# ADMIN STUDENT MANAGEMENT
# =========================================================

@app.route('/admin/add_student', methods=["POST"])
def add_student():

    data = request.get_json()

    uid = get_next_id("users")

    db.users.insert_one({
        "_id": uid,
        "reg_id": uid,
        "full_name": data["name"],
        "username": data["user"],
        "password_hash": generate_password_hash(data["pass"]),
        "role": "CANDIDATE"
    })

    return jsonify({"status": "ok"})


@app.route('/admin/delete_student/<int:id>')
def delete_student(id):

    db.users.delete_one({"reg_id": id})

    return jsonify({"status": "deleted"})


# =========================================================
# ADMIN INVIGILATOR MANAGEMENT
# =========================================================

@app.route('/admin/add_invigilator', methods=["POST"])
def add_invigilator():

    data = request.get_json()

    uid = get_next_id("users")

    db.users.insert_one({
        "_id": uid,
        "reg_id": uid,
        "full_name": data["name"],
        "username": data["user"],
        "password_hash": generate_password_hash(data["pass"]),
        "role": "INVIGILATOR"
    })

    return jsonify({"status": "ok"})


@app.route('/admin/delete_invigilator/<int:id>')
def delete_invigilator(id):

    db.users.delete_one({"reg_id": id})

    return jsonify({"status": "deleted"})


# =========================================================
# INVIGILATOR DASHBOARD
# =========================================================

@app.route('/invigilator/dashboard')
def invigilator_dashboard():

    if session.get("role") != "INVIGILATOR":
        return redirect("/login")

    exams = list(db.exams.find())
    sessions = list(db.exam_sessions.find())

    return render_template(
        "invigilator_dashboard.html",
        exams=exams,
        sessions=sessions
    )


# =========================================================
# EXAM MANAGEMENT
# =========================================================

@app.route('/invigilator/create_exam', methods=["POST"])
def create_exam():

    data = request.get_json()

    exam_id = get_next_id("exams")

    db.exams.insert_one({
        "_id": exam_id,
        "exam_id": exam_id,
        "exam_name": data["name"]
    })

    return jsonify({"status": "created"})


@app.route('/invigilator/delete_exam/<int:id>')
def delete_exam(id):

    db.exams.delete_one({"exam_id": id})

    return jsonify({"status": "deleted"})


# =========================================================
# EXAM SESSION CONTROL
# =========================================================

@app.route('/invigilator/start_exam/<int:session_id>')
def start_exam(session_id):

    db.exam_sessions.update_one(
        {"session_id": session_id},
        {"$set": {"status": "STARTED"}}
    )

    return jsonify({"status": "started"})


@app.route('/invigilator/end_exam/<int:session_id>')
def end_exam(session_id):

    db.exam_sessions.update_one(
        {"session_id": session_id},
        {"$set": {"status": "ENDED"}}
    )

    return jsonify({"status": "ended"})


@app.route('/invigilator/get_sessions/<int:exam_id>')
def get_sessions(exam_id):

    sessions = list(db.exam_sessions.find({"exam_id": exam_id}))

    data = []

    for s in sessions:

        data.append({
            "candidate_id": s["candidate_id"],
            "session_id": s["session_id"],
            "status": s["status"]
        })

    return jsonify(data)


# =========================================================
# QUESTION CRUD
# =========================================================

@app.route('/invigilator/get_questions/<int:exam_id>')
def get_questions(exam_id):

    questions = list(db.questions.find({"exam_id": exam_id}))

    data = []

    for q in questions:

        data.append({
            "id": q["_id"],
            "text": q["question_text"]
        })

    return jsonify(data)


@app.route('/invigilator/add_question', methods=["POST"])
def add_question():

    exam_id = int(request.form["exam_id"])
    text = request.form["text"]

    qid = get_next_id("questions")

    db.questions.insert_one({
        "_id": qid,
        "exam_id": exam_id,
        "question_text": text
    })

    return jsonify({"status": "added"})


@app.route('/invigilator/delete_question/<int:id>')
def delete_question(id):

    db.questions.delete_one({"_id": id})

    return jsonify({"status": "deleted"})


# =========================================================
# ANSWER EVALUATION
# =========================================================

@app.route('/invigilator/get_answers/<int:session_id>')
def get_answers(session_id):

    answers = list(db.answers.find({"session_id": session_id}))

    data = []

    for a in answers:

        q = db.questions.find_one({"_id": a["question_id"]})

        data.append({
            "answer_id": a["_id"],
            "question": q["question_text"],
            "answer": a["answer_text"],
            "marks": a.get("marks", 0)
        })

    return jsonify(data)


@app.route('/invigilator/save_marks', methods=["POST"])
def save_marks():

    answer_id = int(request.form["answer_id"])
    marks = int(request.form["marks"])

    db.answers.update_one(
        {"_id": answer_id},
        {"$set": {"marks": marks}}
    )

    return jsonify({"status": "saved"})


# =========================================================
# STUDENT DASHBOARD
# =========================================================

@app.route('/student/dashboard')
def student_dashboard():

    if session.get("role") != "CANDIDATE":
        return redirect("/login")

    user_id = session["user_id"]

    candidate = db.candidates.find_one({"reg_id": user_id})

    sessions = list(db.exam_sessions.find({"candidate_id": candidate["_id"]}))

    performance = []

    for s in sessions:

        answers = list(db.answers.find({"session_id": s["session_id"]}))

        marks = sum(a.get("marks", 0) for a in answers)

        exam = db.exams.find_one({"exam_id": s["exam_id"]})

        performance.append({
            "exam_name": exam["exam_name"],
            "marks": marks
        })

    return render_template(
        "student_dashboard.html",
        active_session=None,
        performance_data=performance
    )


# =========================================================
# STUDENT EXAM APIs
# =========================================================

@app.route('/api/questions')
def api_questions():

    exam = db.exams.find_one()

    questions = list(db.questions.find({"exam_id": exam["exam_id"]}))

    data = []

    for q in questions:
        data.append({
            "id": q["_id"],
            "text": q["question_text"]
        })

    return jsonify(data)


@app.route('/api/save_answer', methods=["POST"])
def save_answer():

    data = request.get_json()

    aid = get_next_id("answers")

    db.answers.insert_one({
        "_id": aid,
        "session_id": session["exam_session_id"],
        "question_id": data["question_id"],
        "answer_text": data["answer"],
        "marks": 0
    })

    return jsonify({"status": "saved"})


@app.route('/api/start_exam')
def api_start_exam():

    exam = db.exams.find_one()

    sid = get_next_id("exam_sessions")

    db.exam_sessions.insert_one({
        "_id": sid,
        "session_id": sid,
        "exam_id": exam["exam_id"],
        "candidate_id": session["user_id"],
        "status": "STARTED"
    })

    session["exam_session_id"] = sid

    return jsonify({"session_id": sid})


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    app.run(debug=True)