from app import app
from models import db, Registration, Candidate, Exam, Question
from werkzeug.security import generate_password_hash

with app.app_context():

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
    # SAMPLE EXAM
    # -----------------------------
    exam = Exam(
        exam_name="Sample Voice Exam",
        duration=30,
        total_marks=100,
        created_by=invigilator.reg_id
    )
    db.session.add(exam)
    db.session.commit()

    # -----------------------------
    # SAMPLE QUESTIONS
    # -----------------------------
    questions = [
        Question(exam_id=exam.exam_id, question_text="What is photosynthesis?"),
        Question(exam_id=exam.exam_id, question_text="Define computer network."),
        Question(exam_id=exam.exam_id, question_text="Explain the concept of operating systems.")
    ]

    db.session.add_all(questions)
    db.session.commit()

    print("Database seeded successfully!")
    print("Use these credentials to login:")
    print("Candidate -> student / student123")
    print("Invigilator -> invigilator / invigilator123")
