import logging
import os
import secrets
import threading
import time
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.routers import auth, interviews, resumes

BASE_DIR = Path(__file__).resolve().parent
SESSION_LOG_DIR = Path(os.getenv("APP_LOG_DIR", BASE_DIR.parent / "logs" / "user_sessions"))
_session_loggers: dict[tuple[str, str], logging.Logger] = {}
_session_loggers_lock = threading.Lock()
app = FastAPI(title="AI Resume Analyzer", version="1.0.0")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET") or secrets.token_urlsafe(48),
    max_age=8 * 60 * 60,
    same_site="lax",
    https_only=os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true",
)
app.include_router(auth.router)
app.include_router(resumes.router)
app.include_router(interviews.router)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


def _get_session_logger(session: dict) -> logging.Logger | None:
    try:
        user_id = str(uuid.UUID(session.get("user_id", "")))
        session_id = str(uuid.UUID(session.get("login_session_id", "")))
    except (ValueError, TypeError, AttributeError):
        return None

    key = (user_id, session_id)
    with _session_loggers_lock:
        if key not in _session_loggers:
            log_dir = SESSION_LOG_DIR / user_id
            log_dir.mkdir(parents=True, exist_ok=True)
            logger = logging.getLogger(f"app.user_session.{user_id}.{session_id}")
            logger.setLevel(logging.INFO)
            logger.propagate = False
            handler = RotatingFileHandler(
                log_dir / f"{session_id}.log",
                maxBytes=2 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            logger.addHandler(handler)
            _session_loggers[key] = logger
        return _session_loggers[key]


@app.middleware("http")
async def log_user_session_requests(request, call_next):
    request_id = uuid.uuid4().hex[:12]
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger = _get_session_logger(request.session)
        if logger:
            logger.exception(
                "request_failed request_id=%s method=%s path=%s",
                request_id,
                request.method,
                request.url.path,
            )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error.", "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )

    response.headers["X-Request-ID"] = request_id
    logger = _get_session_logger(request.session)
    if logger:
        duration_ms = (time.perf_counter() - started_at) * 1000
        log_method = logger.error if response.status_code >= 500 else logger.warning if response.status_code >= 400 else logger.info
        log_method(
            "request_completed request_id=%s method=%s path=%s status=%s duration_ms=%.1f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
    return response


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(BASE_DIR / "static" / "index.html")