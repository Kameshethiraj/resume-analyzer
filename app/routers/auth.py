import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from psycopg2 import errors
from psycopg2.extensions import connection as DatabaseConnection

from app.auth import establish_session, get_current_user, require_csrf
from app.database import get_db
from app.security import hash_password, verify_password
from app.web_schemas import Credentials

router = APIRouter(prefix="/api/auth", tags=["authentication"])
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: Credentials, connection: DatabaseConnection = Depends(get_db)):
    email = payload.email.strip().lower()
    if not EMAIL_PATTERN.fullmatch(email):
        raise HTTPException(status_code=422, detail="Enter a valid email address.")
    user_id = uuid.uuid4()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO users (id, email, password_hash) VALUES (%s, %s, %s)",
                (user_id, email, hash_password(payload.password)),
            )
        connection.commit()
    except errors.UniqueViolation:
        connection.rollback()
        raise HTTPException(status_code=409, detail="An account with that email already exists.")
    return {"id": str(user_id), "email": email}


@router.post("/login")
def login(payload: Credentials, request: Request, connection: DatabaseConnection = Depends(get_db)):
    email = payload.email.strip().lower()
    with connection.cursor() as cursor:
        cursor.execute("SELECT id, email, password_hash FROM users WHERE email = %s", (email,))
        row = cursor.fetchone()
    if row is None or not verify_password(row[2], payload.password):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    csrf_token = establish_session(request, row[0])
    return {"id": str(row[0]), "email": row[1], "csrf_token": csrf_token}


@router.get("/me")
def me(request: Request, user: dict = Depends(get_current_user)):
    csrf_token = request.session.get("csrf_token")
    if not csrf_token:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return {"id": str(user["id"]), "email": user["email"], "csrf_token": csrf_token}


@router.post("/logout", dependencies=[Depends(require_csrf)])
def logout(request: Request, _user: dict = Depends(get_current_user)):
    request.session.clear()
    return {"message": "Logged out."}