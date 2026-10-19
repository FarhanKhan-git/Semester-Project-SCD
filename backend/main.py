"""
main.py
The VivaVoice server (Python + FastAPI).
 
It does two jobs:
  1. Serves the HTML/CSS pages from the "frontend" folder.
  2. Provides an API (/api/...) that the pages call to read and save data
     in the local MongoDB database.
 
Run it from inside the backend folder:
    uvicorn main:app --reload
Then open http://localhost:8000 in Chrome.
"""
 
import datetime
import random
import string
from pathlib import Path
 
from bson import ObjectId
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
 
import ai_engine
import documents
from auth import (check_password, create_token, current_user, hash_password,
                  password_problems, require_role)
from database import attempts, chunks, exams, to_json, users
 
app = FastAPI(title="VivaVoice API")
FRONTEND = Path(__file__).resolve().parent.parent / "frontend"
 
 
def now():
    return datetime.datetime.utcnow()
 
 
def oid(value: str):
    try:
        return ObjectId(value)
    except Exception:
        raise HTTPException(404, "Not found.")
 
 
# ---------------------------------------------------------------------------
# Default admin account (created the first time the server starts)
# ---------------------------------------------------------------------------
@app.on_event("startup")
def create_default_admin():
    try:
        admin = users.find_one({"role": "admin"})
    except Exception:
        print("\n*** Cannot connect to MongoDB at mongodb://localhost:27017 ***")
        print("*** Start the MongoDB service on your laptop, then run the server again. ***\n")
        raise
    if not admin:
        users.insert_one({
            "name": "System Admin",
            "email": "admin@vivavoice.local",
            "password": hash_password("Admin@123"),
            "role": "admin",
            "created_at": now(),
        })
 
 
# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------
class RegisterBody(BaseModel):
    name: str
    email: str
    password: str
    role: str  # "examiner" or "student"
 
 
class LoginBody(BaseModel):
    email: str
    password: str
 
 
def public_user(user):
    user = to_json(user)
    user.pop("password", None)
    return user
 
 
@app.post("/api/register")
def register(body: RegisterBody):
    if body.role not in ("examiner", "student"):
        raise HTTPException(400, "Role must be examiner or student.")
    missing = password_problems(body.password)
    if missing:
        raise HTTPException(400, "Password must contain " + ", ".join(missing) + ".")
    email = body.email.strip().lower()
    if users.find_one({"email": email}):
        raise HTTPException(400, "An account with this email already exists.")
    result = users.insert_one({
        "name": body.name.strip(),
        "email": email,
        "password": hash_password(body.password),
        "role": body.role,
        "created_at": now(),
    })
    user = users.find_one({"_id": result.inserted_id})
    return {"token": create_token(str(user["_id"]), user["role"]), "user": public_user(user)}
 
 
@app.post("/api/login")
def login(body: LoginBody):
    user = users.find_one({"email": body.email.strip().lower()})
    if not user or not check_password(body.password, user["password"]):
        raise HTTPException(400, "Incorrect email or password.")
    return {"token": create_token(str(user["_id"]), user["role"]), "user": public_user(user)}
 
 
@app.get("/api/me")
def me(user=Depends(current_user)):
    return public_user(user)
 
 
# ---------------------------------------------------------------------------
# Exams (examiner)
# ---------------------------------------------------------------------------
def new_exam_code():
    while True:
        code = "VV-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
        if not exams.find_one({"code": code}):
            return code
 
 
def save_exam_with_document(owner, title, course, num_questions, difficulty,
                            time_per_answer, file_name, file_bytes, practice=False):
    """Shared by 'Create Exam' and 'Practice Mode'."""
    try:
        text = documents.extract_text(file_name, file_bytes)
    except ValueError as error:
        raise HTTPException(400, str(error))
    pieces = documents.split_into_chunks(text)
    if len(pieces) < 3:
        raise HTTPException(400, "The document is too short. Please upload a document with more text.")
 
    exam_id = exams.insert_one({
        "title": title,
        "course": course,
        "owner_id": owner["_id"],
        "owner_name": owner["name"],
        "code": new_exam_code(),
        "num_questions": min(num_questions, len(pieces)),
        "difficulty": difficulty,
        "time_per_answer": time_per_answer,
        "file_name": file_name,
        "word_count": len(text.split()),
        "chunk_count": len(pieces),
        "status": "Active",
        "published": practice,   # practice results are visible immediately
        "practice": practice,
        "created_at": now(),
    }).inserted_id
 
    chunks.insert_many([
        {"exam_id": exam_id, "index": i, "text": piece} for i, piece in enumerate(pieces)
    ])
    return exam_id
 
 
@app.post("/api/exams")
async def create_exam(
    title: str = Form(...),
    course: str = Form(""),
    num_questions: int = Form(5),
    difficulty: str = Form("Medium"),
    time_per_answer: int = Form(90),
    file: UploadFile = File(...),
    user=Depends(current_user),
):
    require_role(user, "examiner")
    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(400, "File is larger than 20 MB.")
    exam_id = save_exam_with_document(user, title, course, num_questions, difficulty,
                                      time_per_answer, file.filename, data)
    return to_json(exams.find_one({"_id": exam_id}))
 
 
@app.get("/api/exams")
def my_exams(user=Depends(current_user)):
    require_role(user, "examiner")
    result = []
    for exam in exams.find({"owner_id": user["_id"], "practice": False}).sort("created_at", -1):
        item = to_json(exam)
        item["attempt_count"] = attempts.count_documents({"exam_id": exam["_id"]})
        result.append(item)
    return result
 
 
@app.get("/api/exams/{exam_id}")
def exam_details(exam_id: str, user=Depends(current_user)):
    exam = exams.find_one({"_id": oid(exam_id)})
    if not exam or (exam["owner_id"] != user["_id"] and user["role"] != "admin"):
        raise HTTPException(404, "Exam not found.")
    item = to_json(exam)
    item["attempts"] = [
        summary(a) for a in attempts.find({"exam_id": exam["_id"]}).sort("started_at", -1)
    ]
    return item
 
 
@app.post("/api/exams/{exam_id}/publish")
def publish_results(exam_id: str, user=Depends(current_user)):
    require_role(user, "examiner")
    exams.update_one({"_id": oid(exam_id), "owner_id": user["_id"]},
                     {"$set": {"published": True}})
    return {"ok": True}
 
 
@app.post("/api/exams/{exam_id}/close")
def close_exam(exam_id: str, user=Depends(current_user)):
    require_role(user, "examiner")
    exams.update_one({"_id": oid(exam_id), "owner_id": user["_id"]},
                     {"$set": {"status": "Closed"}})
    return {"ok": True}
 
 
@app.delete("/api/exams/{exam_id}")
def delete_exam(exam_id: str, user=Depends(current_user)):
    require_role(user, "examiner", "admin")
    exam = exams.find_one({"_id": oid(exam_id)})
    if not exam or (exam["owner_id"] != user["_id"] and user["role"] != "admin"):
        raise HTTPException(404, "Exam not found.")
    chunks.delete_many({"exam_id": exam["_id"]})
    attempts.delete_many({"exam_id": exam["_id"]})
    exams.delete_one({"_id": exam["_id"]})
    return {"ok": True}
 
 
# ---------------------------------------------------------------------------
# Attempts (student takes the exam)
# ---------------------------------------------------------------------------
def summary(attempt):
    """Short version of an attempt, used in tables."""
    answered = [q for q in attempt["questions"] if q.get("answer") is not None]
    total = sum(q.get("final_score", 0) or 0 for q in answered)
    return {
        "id": str(attempt["_id"]),
        "exam_id": str(attempt["exam_id"]),
        "exam_title": attempt.get("exam_title", ""),
        "student_name": attempt["student_name"],
        "status": attempt["status"],
        "score": total,
        "max_score": 10 * len(attempt["questions"]),
        "flags": len(attempt.get("flags", [])),
        "started_at": attempt["started_at"].isoformat(),
        "practice": attempt.get("practice", False),
    }
 
 
def start_attempt_for(exam, student):
    # Pick different random chunks for every student (fairness + anti-cheating)
    all_chunks = list(chunks.find({"exam_id": exam["_id"]}))
    picked = random.sample(all_chunks, exam["num_questions"])
    questions = []
    for i, c in enumerate(picked):
        asked = [q["question"] for q in questions]   # avoid repeating a topic
        questions.append({
            "number": i + 1,
            "chunk_index": c["index"],
            "source": c["text"],
            "question": ai_engine.generate_question(c["text"], exam["difficulty"], asked),
            "answer": None,
        })
 
    attempt_id = attempts.insert_one({
        "exam_id": exam["_id"],
        "exam_title": exam["title"],
        "student_id": student["_id"],
        "student_name": student["name"],
        "questions": questions,
        "flags": [],
        "status": "In Progress",
        "practice": exam.get("practice", False),
        "started_at": now(),
    }).inserted_id
    return str(attempt_id)
 
 
class JoinBody(BaseModel):
    code: str
 
 
@app.post("/api/attempts/start")
def start_attempt(body: JoinBody, user=Depends(current_user)):
    require_role(user, "student")
    exam = exams.find_one({"code": body.code.strip().upper(), "practice": False})
    if not exam:
        raise HTTPException(404, "No exam found with this code.")
    if exam["status"] != "Active":
        raise HTTPException(400, "This exam is closed.")
    if attempts.find_one({"exam_id": exam["_id"], "student_id": user["_id"]}):
        raise HTTPException(400, "You have already taken this exam.")
    return {"attempt_id": start_attempt_for(exam, user)}
 
 
@app.post("/api/practice")
async def start_practice(
    difficulty: str = Form("Medium"),
    num_questions: int = Form(5),
    file: UploadFile = File(...),
    user=Depends(current_user),
):
    require_role(user, "student")
    data = await file.read()
    exam_id = save_exam_with_document(user, "Practice: " + file.filename, "Practice Mode",
                                      num_questions, difficulty, 120, file.filename, data,
                                      practice=True)
    return {"attempt_id": start_attempt_for(exams.find_one({"_id": exam_id}), user)}
 
 
def get_attempt(attempt_id, user):
    attempt = attempts.find_one({"_id": oid(attempt_id)})
    if not attempt:
        raise HTTPException(404, "Attempt not found.")
    exam = exams.find_one({"_id": attempt["exam_id"]})
    is_student = attempt["student_id"] == user["_id"]
    is_examiner = exam and exam["owner_id"] == user["_id"]
    if not (is_student or is_examiner or user["role"] == "admin"):
        raise HTTPException(403, "Not allowed.")
    return attempt, exam, is_student
 
 
@app.get("/api/attempts/{attempt_id}/exam-room")
def exam_room_data(attempt_id: str, user=Depends(current_user)):
    """What the student sees DURING the exam: questions only, no sources or scores."""
    attempt, exam, is_student = get_attempt(attempt_id, user)
    if not is_student:
        raise HTTPException(403, "Only the student can open the exam room.")
    return {
        "exam_title": exam["title"],
        "time_per_answer": exam["time_per_answer"],
        "status": attempt["status"],
        "questions": [{"number": q["number"], "question": q["question"],
                       "answered": q["answer"] is not None} for q in attempt["questions"]],
    }
 
 
class AnswerBody(BaseModel):
    number: int
    answer: str
    typed: bool = False
    seconds_taken: int = 0
 
 
@app.post("/api/attempts/{attempt_id}/answer")
def submit_answer(attempt_id: str, body: AnswerBody, user=Depends(current_user)):
    attempt, exam, is_student = get_attempt(attempt_id, user)
    if not is_student or attempt["status"] != "In Progress":
        raise HTTPException(400, "This exam is not in progress.")
    q = attempt["questions"][body.number - 1]
    grade = ai_engine.grade_answer(body.answer, q["source"])
    q.update({
        "answer": body.answer,
        "typed": body.typed,
        "seconds_taken": body.seconds_taken,
        "ai_score": grade["score"],
        "final_score": grade["score"],
        "verdict": grade["verdict"],
        "reason": grade["reason"],
        "overridden": False,
    })
    attempts.update_one({"_id": attempt["_id"]}, {"$set": {"questions": attempt["questions"]}})
    return {"ok": True}
 
 
class FlagBody(BaseModel):
    type: str
 
 
@app.post("/api/attempts/{attempt_id}/flag")
def add_flag(attempt_id: str, body: FlagBody, user=Depends(current_user)):
    attempt, exam, is_student = get_attempt(attempt_id, user)
    attempts.update_one({"_id": attempt["_id"]},
                        {"$push": {"flags": {"type": body.type, "time": now().isoformat()}}})
    return {"ok": True}
 
 
@app.post("/api/attempts/{attempt_id}/finish")
def finish_attempt(attempt_id: str, user=Depends(current_user)):
    attempt, exam, is_student = get_attempt(attempt_id, user)
    attempts.update_one({"_id": attempt["_id"]},
                        {"$set": {"status": "Completed", "finished_at": now()}})
    return {"ok": True}
 
 
@app.get("/api/attempts/{attempt_id}")
def attempt_result(attempt_id: str, user=Depends(current_user)):
    """Full result. Students only see it after the examiner publishes it."""
    attempt, exam, is_student = get_attempt(attempt_id, user)
    if is_student and not exam.get("published"):
        return {"published": False, "exam_title": exam["title"], "status": attempt["status"]}
    item = summary(attempt)
    item.update({
        "published": True,
        "questions": attempt["questions"],
        "flag_list": attempt.get("flags", []),
        "difficulty": exam["difficulty"],
        "file_name": exam["file_name"],
        "can_override": (not is_student) and exam["owner_id"] == user["_id"],
    })
    return item
 
 
class OverrideBody(BaseModel):
    number: int
    score: int
 
 
@app.post("/api/attempts/{attempt_id}/override")
def override_score(attempt_id: str, body: OverrideBody, user=Depends(current_user)):
    attempt, exam, is_student = get_attempt(attempt_id, user)
    if exam["owner_id"] != user["_id"]:
        raise HTTPException(403, "Only the examiner can change scores.")
    if not 0 <= body.score <= 10:
        raise HTTPException(400, "Score must be between 0 and 10.")
    q = attempt["questions"][body.number - 1]
    q["final_score"] = body.score
    q["overridden"] = body.score != q.get("ai_score")
    attempts.update_one({"_id": attempt["_id"]}, {"$set": {"questions": attempt["questions"]}})
    return {"ok": True}
 
 
@app.get("/api/my-attempts")
def my_attempts(user=Depends(current_user)):
    require_role(user, "student")
    result = []
    for a in attempts.find({"student_id": user["_id"]}).sort("started_at", -1):
        item = summary(a)
        exam = exams.find_one({"_id": a["exam_id"]})
        item["published"] = bool(exam and exam.get("published"))
        result.append(item)
    return result
 
 
# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------
@app.get("/api/admin/overview")
def admin_overview(user=Depends(current_user)):
    require_role(user, "admin")
    return {
        "examiners": users.count_documents({"role": "examiner"}),
        "students": users.count_documents({"role": "student"}),
        "exams": exams.count_documents({"practice": False}),
        "attempts": attempts.count_documents({}),
        "users": [public_user(u) for u in users.find().sort("created_at", -1)],
    }
 
 
@app.delete("/api/admin/users/{user_id}")
def delete_user(user_id: str, user=Depends(current_user)):
    require_role(user, "admin")
    if oid(user_id) == user["_id"]:
        raise HTTPException(400, "You cannot delete your own account.")
    users.delete_one({"_id": oid(user_id)})
    return {"ok": True}
 
 
# ---------------------------------------------------------------------------
# Serve the HTML pages (must be the LAST line so /api routes work first)
# ---------------------------------------------------------------------------
app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")