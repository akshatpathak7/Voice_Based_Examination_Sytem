from app import app
from models import db, Registration, Candidate, Exam, Question
from werkzeug.security import generate_password_hash
from crypto_utils import generate_exam_key, encrypt_exam_key, load_master_key

with app.app_context():

    master_key = load_master_key()

    # -----------------------------
    # INVIGILATOR USER
    # -----------------------------
    invigilator = Registration(
        full_name="Demo Invigilator",
        username="invigilator",
        email="invigilator@test.com",
        password_hash=generate_password_hash("invigilator123"),
        role="INVIGILATOR"
    )
    db.session.add(invigilator)
    db.session.commit()

    # -----------------------------
    # CANDIDATE USER
    # -----------------------------
    candidate_user = Registration(
        full_name="Demo Candidate",
        username="student",
        email="student@test.com",
        password_hash=generate_password_hash("student123"),
        role="CANDIDATE",
        phone_no="9999999999"
    )
    db.session.add(candidate_user)
    db.session.commit()

    # -----------------------------
    # CANDIDATE PROFILE ENTRY
    # -----------------------------
    candidate = Candidate(
        reg_id=candidate_user.reg_id,
        registration_no="CAND-001"
    )
    db.session.add(candidate)
    db.session.commit()

    # -----------------------------
    # SAMPLE PHYSICS EXAM (with encrypted key)
    # -----------------------------
    exam_key = generate_exam_key()
    enc_ct, enc_iv, enc_tag = encrypt_exam_key(exam_key, master_key)

    exam = Exam(
        exam_name="Physics – Demo Subjective Exam",
        duration=60,
        total_marks=100,
        created_by=invigilator.reg_id,
        enc_key_ciphertext=enc_ct,
        enc_key_iv=enc_iv,
        enc_key_tag=enc_tag,
    )
    db.session.add(exam)
    db.session.commit()

    # -----------------------------
    # SAMPLE PHYSICS SUBJECTIVE QUESTIONS
    # -----------------------------
    questions = [
        Question(
            exam_id=exam.exam_id,
            question_text="State Newton's three laws of motion and illustrate each law with a suitable example."
        ),
        Question(
            exam_id=exam.exam_id,
            question_text="Explain the principle of conservation of energy with reference to the motion of a simple pendulum."
        ),
        Question(
            exam_id=exam.exam_id,
            question_text="What is refraction of light? Describe an everyday situation where refraction plays an important role and explain it scientifically."
        ),
        Question(
            exam_id=exam.exam_id,
            question_text="Define electric current, potential difference, and resistance. Explain the relationship between them using Ohm's law."
        ),
        Question(
            exam_id=exam.exam_id,
            question_text="Describe the difference between longitudinal and transverse waves, and give one real-world example of each type."
        )
    ]

    db.session.add_all(questions)
    db.session.commit()

    print("Database seeded successfully!")
    print("Use these credentials to login:")
    print("Candidate -> student / student123")
    print("Invigilator -> invigilator / invigilator123")
