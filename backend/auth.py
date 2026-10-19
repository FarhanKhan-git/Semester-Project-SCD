"""
auth.py
Handles passwords and login tokens.
 
- Passwords are never saved as plain text. bcrypt turns them into a hash.
- After login, the server gives the browser a JWT token. The browser sends
  this token with every request so the server knows who is asking.
"""
 
import datetime
import bcrypt
import jwt
from bson import ObjectId
from fastapi import Header, HTTPException
 
from database import users
 
SECRET_KEY = "change-this-secret-key-before-deployment"
TOKEN_HOURS = 12
 
 
def password_problems(password: str):
    """Password rule: at least 8 characters, one uppercase letter,
    one number and one special character. Returns what is missing."""
    problems = []
    if len(password) < 8:
        problems.append("at least 8 characters")
    if not any(c.isupper() for c in password):
        problems.append("one uppercase letter")
    if not any(c.isdigit() for c in password):
        problems.append("one number")
    if not any(not c.isalnum() and not c.isspace() for c in password):
        problems.append("one special character (e.g. @ # $ !)")
    return problems
 
 
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
 
 
def check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())
 
 
def create_token(user_id: str, role: str) -> str:
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=TOKEN_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")
 
 
def current_user(authorization: str = Header(default="")):
    """Reads the 'Authorization: Bearer <token>' header and returns the user.
    FastAPI calls this automatically for any route that needs a logged-in user."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Please log in first.")
    token = authorization.replace("Bearer ", "")
    try:
        data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Your session has expired. Please log in again.")
    user = users.find_one({"_id": ObjectId(data["user_id"])})
    if not user:
        raise HTTPException(401, "User not found.")
    return user
 
 
def require_role(user, *roles):
    if user["role"] not in roles:
        raise HTTPException(403, "You do not have permission for this page.")