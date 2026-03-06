"""
Seed a demo completed exam session for the existing demo candidate,
so the examiner can test AI and manual grading features.
"""

from app import app
from models import get_db, get_next_id
from crypto_utils import (
    load_master_key,
    decrypt_exam_key,
    encrypt_answer,
    compute_integrity_hash,
)
from datetime import datetime, timezone

with app.app_context():
    db = get_db()
    master_key = load_master_key()

    # ---- Find existing candidate & exam ----
    candidate = db.candidates.find_one({"registration_no": "CAND-001"})
    if not candidate:
        print("ERROR: Demo candidate CAND-001 not found. Run seed.py first.")
        exit(1)

    exam = db.exams.find_one()
    if not exam:
        print("ERROR: No exam found. Run seed.py first.")
        exit(1)

    # ---- Decrypt the exam key ----
    exam_key = decrypt_exam_key(
        bytes(exam["enc_key_ciphertext"]),
        bytes(exam["enc_key_iv"]),
        bytes(exam["enc_key_tag"]),
        master_key,
    )

    # ---- Create a completed exam session ----
    session_id = get_next_id("exam_sessions")
    now = datetime.now(timezone.utc)
    db.exam_sessions.insert_one({
        "_id": session_id,
        "exam_id": exam["_id"],
        "candidate_id": candidate["_id"],
        "start_time": now,
        "end_time": now,
        "status": "COMPLETED",
    })

    # ---- Get all questions for this exam ----
    questions = list(db.questions.find({"exam_id": exam["_id"]}))

    # ---- Demo answers (realistic student responses) ----
    demo_answers = {
        "Newton": (
            "Newton's first law states that an object at rest stays at rest and an object "
            "in motion stays in motion unless acted upon by an external force. For example, "
            "a book lying on a table remains stationary until someone pushes it. The second "
            "law states that force equals mass times acceleration (F=ma). For instance, a "
            "heavier cart requires more force to accelerate at the same rate as a lighter one. "
            "The third law states that for every action there is an equal and opposite reaction. "
            "When you jump off a boat, the boat moves backward as you move forward."
        ),
        "conservation of energy": (
            "The principle of conservation of energy states that energy can neither be created "
            "nor destroyed, only transformed from one form to another. In a simple pendulum, "
            "at the highest point the bob has maximum potential energy and zero kinetic energy. "
            "As it swings down, potential energy converts to kinetic energy. At the lowest point "
            "the kinetic energy is maximum and potential energy is minimum. The total mechanical "
            "energy remains constant throughout the motion, ignoring air resistance and friction."
        ),
        "refraction": (
            "Refraction is the bending of light as it passes from one medium to another with "
            "a different optical density. This happens because the speed of light changes in "
            "different media. A common everyday example is when a straw in a glass of water "
            "appears to be bent at the water surface. This occurs because light travelling from "
            "water to air changes speed and direction at the boundary. Snell's law governs the "
            "relationship between the angles of incidence and refraction."
        ),
        "electric current": (
            "Electric current is the rate of flow of electric charge through a conductor, measured "
            "in amperes. Potential difference is the work done per unit charge in moving a charge "
            "between two points, measured in volts. Resistance is the opposition to the flow of "
            "current in a conductor, measured in ohms. According to Ohm's law, V equals I times R, "
            "where V is potential difference, I is current, and R is resistance. This means current "
            "is directly proportional to voltage and inversely proportional to resistance."
        ),
        "longitudinal": (
            "In longitudinal waves, the particles of the medium vibrate parallel to the direction "
            "of wave propagation. Sound waves are an example of longitudinal waves where air "
            "molecules compress and expand along the direction of travel. In transverse waves, "
            "the particles vibrate perpendicular to the direction of propagation. Light waves "
            "and water surface waves are examples of transverse waves. The key difference is "
            "the direction of particle oscillation relative to the wave's direction of travel."
        ),
    }

    # ---- Insert encrypted answers ----
    for q in questions:
        q_text = q["question_text"]

        # Find matching demo answer
        answer_text = "This is a placeholder answer for the question."
        for keyword, ans in demo_answers.items():
            if keyword.lower() in q_text.lower():
                answer_text = ans
                break

        # Encrypt and store
        ciphertext, iv, tag = encrypt_answer(answer_text, exam_key)
        encrypted_at = datetime.now(timezone.utc)
        integrity = compute_integrity_hash(
            master_key, answer_text, q["_id"], session_id, encrypted_at
        )

        answer_id = get_next_id("answers")
        db.answers.insert_one({
            "_id": answer_id,
            "session_id": session_id,
            "question_id": q["_id"],
            "answer_ciphertext": ciphertext,
            "answer_iv": iv,
            "answer_tag": tag,
            "integrity_hash": integrity,
            "encrypted_at": encrypted_at,
            "marks": None,
        })

    print(f"Demo exam session created (session_id: {session_id})")
    print(f"  Candidate: CAND-001 (Demo Candidate)")
    print(f"  Exam: {exam['exam_name']}")
    print(f"  Answers inserted: {len(questions)}")
    print()
    print("Login as examiner (examiner / examiner123) to test grading.")
