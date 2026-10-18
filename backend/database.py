"""
database.py
Connects to the LOCAL MongoDB server running on your laptop.

MongoDB stores data as "documents" (like JSON objects) inside "collections"
(like tables). VivaVoice uses 4 collections:

    users     -> examiners, students and admins
    exams     -> exam settings + the uploaded document's name
    chunks    -> small pieces of the uploaded document (used for questions)
    attempts  -> one student's exam: questions, answers, scores, flags
"""

from pymongo import MongoClient

# Default address of MongoDB when installed on your own computer.
MONGO_URL = "mongodb://localhost:27017"
DATABASE_NAME = "vivavoice"

# Give up after 3 seconds if MongoDB is not running, instead of waiting forever
client = MongoClient(MONGO_URL, serverSelectionTimeoutMS=3000)
db = client[DATABASE_NAME]

users = db["users"]
exams = db["exams"]
chunks = db["chunks"]
attempts = db["attempts"]


def to_json(doc):
    """MongoDB uses a special ObjectId for _id. Convert it to a normal string
    so it can be sent to the browser as JSON."""
    if doc is None:
        return None
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    for key, value in doc.items():
        if type(value).__name__ == "ObjectId":
            doc[key] = str(value)
    return doc
