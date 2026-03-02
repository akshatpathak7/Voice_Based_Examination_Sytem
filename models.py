from pymongo import MongoClient, ReturnDocument

_client = None
_db = None


def init_app(app):
    global _client, _db
    mongo_uri = app.config.get("MONGO_URI", "mongodb://localhost:27017/")
    db_name = app.config.get("MONGO_DB_NAME", "exam_db")
    _client = MongoClient(mongo_uri)
    _db = _client[db_name]

    _db.users.create_index("username", unique=True)
    _db.users.create_index("email", unique=True)
    _db.candidates.create_index("registration_no", unique=True)


def get_db():
    return _db


def get_next_id(collection_name):
    """Auto-incrementing integer ID using a counters collection."""
    result = _db.counters.find_one_and_update(
        {"_id": collection_name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return result["seq"]
