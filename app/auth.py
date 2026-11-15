import hmac
import secrets
import uuid

from fastapi import Depends, HTTPException, Request, status
from psycopg2.extensions import connection as DatabaseConnection

from app.database import get_db


def get_current_user(
    request: Request,
    connection: DatabaseConnection = Depends(get_db),
) -> dict:
    user_id = request.session.get("user_id")
    try:
        user_uuid = uuid.UUID(user_id)
    except (TypeError, ValueError, AttributeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    with connection.cursor() as cursor:
        cursor.execute("SELECT id, email FROM users WHERE id = %s", (user_uuid,))
        row = cursor.fetchone()
    if row is None:
        request.session.clear()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    request.session.setdefault("login_session_id", str(uuid.uuid4()))
    return {"id": row[0], "email": row[1]}


def require_csrf(request: Request) -> None:
    expected = request.session.get("csrf_token")
    supplied = request.headers.get("x-csrf-token", "")
    if not expected or not hmac.compare_digest(expected, supplied):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or missing CSRF token.")


def establish_session(request: Request, user_id: uuid.UUID) -> str:
    request.session.clear()
    csrf_token = secrets.token_urlsafe(32)
    request.session.update({
        "user_id": str(user_id),
        "csrf_token": csrf_token,
        "login_session_id": str(uuid.uuid4()),
    })
    return csrf_token