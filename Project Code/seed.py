from app import app
from models import get_db, get_next_id
from werkzeug.security import generate_password_hash
from crypto_utils import generate_exam_key, encrypt_exam_key, load_master_key
from datetime import datetime, timezone

with app.app_context():

    db = get_db()
    master_key = load_master_key()

    # Drop all existing collections for a clean slate
    for col in ("users", "candidates", "exams", "questions",
                "exam_sessions", "answers", "evaluations",
                "examiner_assignments", "counters"):
        db[col].drop()

    # Re-create unique indexes
    db.users.create_index("username", unique=True)
    db.users.create_index("email", unique=True)
    db.candidates.create_index("registration_no", unique=True)

    # -----------------------------
    # INVIGILATOR USER
    # -----------------------------
    inv_id = get_next_id("users")
    db.users.insert_one({
        "_id": inv_id,
        "full_name": "Demo Invigilator",
        "username": "invigilator",
        "email": "invigilator@test.com",
        "password_hash": generate_password_hash("invigilator123"),
        "role": "INVIGILATOR",
        "phone_no": None,
        "created_at": datetime.now(timezone.utc),
        "session_token": None,
    })

    # -----------------------------
    # CANDIDATE USER
    # -----------------------------
    cand_user_id = get_next_id("users")
    db.users.insert_one({
        "_id": cand_user_id,
        "full_name": "Demo Candidate",
        "username": "student",
        "email": "student@test.com",
        "password_hash": generate_password_hash("student123"),
        "role": "CANDIDATE",
        "phone_no": "9999999999",
        "created_at": datetime.now(timezone.utc),
        "session_token": None,
    })

    # -----------------------------
    # EXAMINER USER
    # -----------------------------
    examiner_id = get_next_id("users")
    db.users.insert_one({
        "_id": examiner_id,
        "full_name": "Demo Examiner",
        "username": "examiner",
        "email": "examiner@test.com",
        "password_hash": generate_password_hash("examiner123"),
        "role": "EXAMINER",
        "phone_no": None,
        "created_at": datetime.now(timezone.utc),
        "session_token": None,
    })

    # -----------------------------
    # ADMIN USER
    # -----------------------------
    admin_id = get_next_id("users")
    db.users.insert_one({
        "_id": admin_id,
        "full_name": "Demo Admin",
        "username": "admin",
        "email": "admin@test.com",
        "password_hash": generate_password_hash("admin123"),
        "role": "ADMIN",
        "phone_no": None,
        "created_at": datetime.now(timezone.utc),
        "session_token": None,
    })

    # -----------------------------
    # CANDIDATE PROFILE ENTRY
    # -----------------------------
    cand_id = get_next_id("candidates")
    db.candidates.insert_one({
        "_id": cand_id,
        "reg_id": cand_user_id,
        "registration_no": "CAND-001",
    })

    # -----------------------------
    # SAMPLE PHYSICS EXAM (with encrypted key)
    # -----------------------------
    exam_key = generate_exam_key()
    enc_ct, enc_iv, enc_tag = encrypt_exam_key(exam_key, master_key)

    exam_id = get_next_id("exams")
    db.exams.insert_one({
        "_id": exam_id,
        "exam_name": "Physics \u2013 Demo Subjective Exam",
        "duration": 60,
        "total_marks": 100,
        "created_by": inv_id,
        "enc_key_ciphertext": enc_ct,
        "enc_key_iv": enc_iv,
        "enc_key_tag": enc_tag,
    })

    # -----------------------------
    # EXAMINER ASSIGNMENT (link examiner -> student + exam)
    # -----------------------------
    assign_id = get_next_id("examiner_assignments")
    db.examiner_assignments.insert_one({
        "_id": assign_id,
        "examiner_id": examiner_id,
        "candidate_id": cand_id,
        "exam_id": exam_id,
    })

    # -----------------------------
    # SAMPLE PHYSICS SUBJECTIVE QUESTIONS
    # -----------------------------
    question_texts = [
        "State Newton's three laws of motion and illustrate each law with a suitable example.",
        "Explain the principle of conservation of energy with reference to the motion of a simple pendulum.",
        "What is refraction of light? Describe an everyday situation where refraction plays an important role and explain it scientifically.",
        "Define electric current, potential difference, and resistance. Explain the relationship between them using Ohm's law.",
        "Describe the difference between longitudinal and transverse waves, and give one real-world example of each type.",
    ]

    for text in question_texts:
        q_id = get_next_id("questions")
        db.questions.insert_one({
            "_id": q_id,
            "exam_id": exam_id,
            "question_text": text,
        })

    print("MongoDB seeded successfully!")
    print("Use these credentials to login:")
    print("Candidate   -> student / student123")
    print("Invigilator -> invigilator / invigilator123")
    print("Examiner    -> examiner / examiner123")
    print("Admin       -> admin / admin123")
