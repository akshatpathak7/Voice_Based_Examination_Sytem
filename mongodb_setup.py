from pymongo import MongoClient
from werkzeug.security import generate_password_hash
from datetime import datetime

# CONNECT TO MONGODB

client = MongoClient("mongodb://localhost:27017/")

db = client["voice_exam_system"]

print("Connected to MongoDB")

collections = [
    "users",
    "candidates",
    "exams",
    "questions",
    "exam_sessions",
    "answers",
    "logs"
]

for col in collections:
    if col not in db.list_collection_names():
        db.create_collection(col)
        print(f"Created collection: {col}")

# -----------------------------

# CREATE INDEXES

# -----------------------------

db.users.create_index("username", unique=True)
db.users.create_index("email", unique=True)

db.candidates.create_index("registration_no", unique=True)

print("Indexes created")

# -----------------------------

# CREATE DEFAULT ADMIN

# -----------------------------

admin = db.users.find_one({"username": "admin"})

if not admin:
    db.users.insert_one({
        "full_name": "System Administrator",
        "username": "admin",
        "email": "admin@test.com",
        "password_hash": generate_password_hash("admin123"),
        "role": "ADMIN",
        "created_at": datetime.utcnow()
    })
    print("Admin user created")

else:
    print("Admin already exists")
print("MongoDB setup complete")
