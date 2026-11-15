import asyncio
import io
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.datastructures import UploadFile
from starlette.requests import Request

from app import security
from app import main as main_app
from app.auth import get_current_user
from app.routers import auth as auth_router
from app.routers import interviews, resumes
from app.web_schemas import AnswerSubmission, Credentials


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.one = None
        self.many = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, params=None):
        normalized = " ".join(query.lower().split())
        self.connection.calls.append((normalized, params))
        self.one = None
        self.many = []
        if "from users where email" in normalized:
            self.one = self.connection.login_row
        elif "from users where id" in normalized:
            self.one = self.connection.user_row
        elif "from resumes where id = %s and user_id = %s" in normalized:
            self.one = self.connection.resume_row
        elif "from interview_sessions i" in normalized:
            self.one = self.connection.interview_row
        elif "select id, question_text from interview_questions" in normalized:
            self.one = self.connection.current_question
        elif "select question_text, is_follow_up from interview_questions" in normalized:
            self.many = self.connection.prior_questions
        elif normalized.startswith("select r.id, r.original_filename"):
            self.many = self.connection.resume_rows

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class FakeConnection:
    def __init__(self):
        self.calls = []
        self.commits = 0
        self.rollbacks = 0
        self.login_row = None
        self.user_row = None
        self.resume_row = None
        self.resume_rows = []
        self.interview_row = None
        self.current_question = None
        self.prior_questions = []

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def request_with_session(session=None):
    return Request({"type": "http", "method": "POST", "path": "/", "headers": [], "session": session or {}})


def test_registration_hashes_password_and_login_establishes_session():
    connection = FakeConnection()
    payload = Credentials(email="Candidate@Example.com", password="correct horse battery")
    auth_router.register(payload, connection)
    insert_call = next(call for call in connection.calls if call[0].startswith("insert into users"))
    user_id, email, password_hash = insert_call[1]
    assert email == "candidate@example.com"
    assert password_hash != payload.password
    assert security.verify_password(password_hash, payload.password)

    connection.login_row = (user_id, email, password_hash)
    request = request_with_session()
    result = auth_router.login(payload, request, connection)
    assert result["csrf_token"] == request.session["csrf_token"]
    assert request.session["user_id"] == str(user_id)


def test_login_rejects_invalid_credentials():
    connection = FakeConnection()
    connection.login_row = None
    with pytest.raises(HTTPException) as error:
        auth_router.login(Credentials(email="nobody@example.com", password="wrong-pass"), request_with_session(), connection)
    assert error.value.status_code == 401


def test_authenticated_identity_comes_from_session_and_database():
    user_id = uuid.uuid4()
    connection = FakeConnection()
    connection.user_row = (user_id, "owner@example.com")
    user = get_current_user(request_with_session({"user_id": str(user_id)}), connection)
    assert user == {"id": user_id, "email": "owner@example.com"}
    query, params = connection.calls[-1]
    assert "where id = %s" in query
    assert params == (user_id,)


def test_resume_reads_are_scoped_to_authenticated_owner():
    owner_id = uuid.uuid4()
    connection = FakeConnection()
    connection.resume_rows = [(uuid.uuid4(), "resume.pdf", "completed", __import__("datetime").datetime.now(), 2)]
    resumes.list_resumes({"id": owner_id}, connection)
    query, params = connection.calls[-1]
    assert "where r.user_id = %s" in query
    assert params == (owner_id,)

    other_user = uuid.uuid4()
    resume_id = uuid.uuid4()
    connection.resume_row = None
    with pytest.raises(HTTPException) as error:
        resumes.resume_details(resume_id, {"id": other_user}, connection)
    assert error.value.status_code == 404
    detail_query, detail_params = connection.calls[-1]
    assert "where id = %s and user_id = %s" in detail_query
    assert detail_params == (resume_id, other_user)

    interview_id = uuid.uuid4()
    connection.interview_row = None
    with pytest.raises(HTTPException) as interview_error:
        interviews.current_interview(interview_id, {"id": other_user}, connection)
    assert interview_error.value.status_code == 404
    interview_query, interview_params = connection.calls[-1]
    assert "i.id = %s and i.user_id = %s" in interview_query
    assert interview_params == (interview_id, other_user)


def test_upload_uses_distinct_server_generated_resume_ids(monkeypatch, tmp_path):
    monkeypatch.setenv("RESUME_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(resumes, "extract_text_from_pdf", lambda _path: "Resume text with experience.")
    monkeypatch.setattr(resumes, "embed_texts", lambda chunks: [[0.0] * 384 for _ in chunks])

    async def upload_once():
        connection = FakeConnection()
        uploaded = UploadFile(filename="../../private.pdf", file=io.BytesIO(b"%PDF-1.7 fake"))
        result = await resumes.upload_resume(uploaded, {"id": uuid.uuid4()}, connection)
        insert = next(call for call in connection.calls if call[0].startswith("insert into resumes"))
        assert insert[1][3] == f"{result['id']}.pdf"
        assert "private.pdf" not in insert[1][3]
        assert result["upload_status"] == "completed"
        return result

    first, second = asyncio.run(upload_twice(upload_once))
    assert first["id"] != second["id"]


async def upload_twice(upload_once):
    return await upload_once(), await upload_once()


def test_interview_answer_is_saved_and_advances(monkeypatch):
    user_id = uuid.uuid4()
    interview_id = uuid.uuid4()
    resume_id = uuid.uuid4()
    connection = FakeConnection()
    connection.interview_row = (interview_id, resume_id, "active", 5, 8, 1)
    connection.current_question = (11, "How would you index this query?")
    connection.prior_questions = [("How would you index this query?", False)]
    evaluation = {"score": 8, "strengths": ["Clear trade-off"], "improvements": [],
                  "feedback": "Good explanation.", "follow_up_question": "Why?"}
    monkeypatch.setattr(interviews, "evaluate_interview_answer", lambda *_args: evaluation)
    monkeypatch.setattr(interviews, "generate_session_question", lambda **_kwargs: "How do you validate the plan?")

    response = interviews.submit_answer(
        interview_id,
        AnswerSubmission(answer="I would inspect the query plan."),
        {"id": user_id},
        connection,
    )
    assert response["evaluation"] == evaluation
    assert response["next_question"]["sequence_number"] == 2
    assert response["status"] == "active"
    assert any("i.user_id = %s" in query and params == (interview_id, user_id) for query, params in connection.calls)
    answer_update = next(call for call in connection.calls if call[0].startswith("update interview_questions set candidate_answer"))
    assert answer_update[1][2].adapted == ["Clear trade-off"]
    assert answer_update[1][3].adapted == []


def test_follow_up_threshold_and_overall_cap():
    weak = {"score": 5}
    strong = {"score": 6}
    assert interviews.should_ask_follow_up(weak, 4, 8)
    assert not interviews.should_ask_follow_up(strong, 4, 8)
    assert not interviews.should_ask_follow_up(weak, 8, 8)

    connection = FakeConnection()
    interview_id = uuid.uuid4()
    session = (interview_id, uuid.uuid4(), "active", 5, 2, 2)
    next_question = interviews._create_next_question(connection, session, uuid.uuid4(), weak)
    assert next_question is None
    assert any("set status = 'completed'" in query for query, _ in connection.calls)


def test_unhandled_error_is_logged_to_session_file(monkeypatch, tmp_path):
    monkeypatch.setattr(main_app, "SESSION_LOG_DIR", tmp_path)
    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    request = SimpleNamespace(
        session={"user_id": str(user_id), "login_session_id": str(session_id)},
        method="POST",
        url=SimpleNamespace(path="/api/interviews/test/answers"),
    )

    async def failing_endpoint(_request):
        raise RuntimeError("test failure")

    response = asyncio.run(main_app.log_user_session_requests(request, failing_endpoint))
    log_file = tmp_path / str(user_id) / f"{session_id}.log"
    log_text = log_file.read_text(encoding="utf-8")
    assert response.status_code == 500
    assert response.headers["X-Request-ID"] in log_text
    assert "RuntimeError: test failure" in log_text
    assert "request_failed" in log_text