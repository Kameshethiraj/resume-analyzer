import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg2.extras import Json
from psycopg2.extensions import connection as DatabaseConnection

from app.auth import get_current_user, require_csrf
from app.database import get_db
from app.interview_session import (
    FOLLOW_UP_THRESHOLD,
    evaluate_interview_answer,
    generate_session_question,
    should_ask_follow_up,
)
from app.web_schemas import AnswerSubmission

router = APIRouter(prefix="/api/interviews", tags=["interviews"])
PRIMARY_QUESTION_LIMIT = 5
OVERALL_QUESTION_LIMIT = max(PRIMARY_QUESTION_LIMIT, int(os.getenv("INTERVIEW_QUESTION_LIMIT", "8")))


def _owned_interview(connection, interview_id: uuid.UUID, user_id: uuid.UUID):
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT i.id, i.resume_id, i.status, i.primary_question_limit,
                      i.overall_question_limit, i.questions_asked
               FROM interview_sessions i
               JOIN resumes r ON r.id = i.resume_id AND r.user_id = i.user_id
               WHERE i.id = %s AND i.user_id = %s""",
            (interview_id, user_id),
        )
        return cursor.fetchone()


def _summary(connection, interview_id: uuid.UUID):
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT sequence_number, question_text, is_follow_up, candidate_answer,
                      skipped, score, strengths, improvements, feedback, follow_up_question
               FROM interview_questions WHERE interview_id = %s ORDER BY sequence_number""",
            (interview_id,),
        )
        rows = cursor.fetchall()
    questions = [
        {"sequence_number": row[0], "question": row[1], "is_follow_up": row[2],
         "answer": row[3], "skipped": row[4], "score": row[5], "strengths": row[6],
         "improvements": row[7], "feedback": row[8], "follow_up_question": row[9]}
        for row in rows
    ]
    scores = [item["score"] for item in questions if item["score"] is not None]
    return {"questions": questions, "answered_count": len(scores),
            "average_score": round(sum(scores) / len(scores), 1) if scores else None}


def _complete(connection, interview_id: uuid.UUID) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """UPDATE interview_sessions SET status = 'completed', completed_at = now()
               WHERE id = %s AND status = 'active'""",
            (interview_id,),
        )


def _create_next_question(connection, interview, user_id: uuid.UUID, evaluation: dict | None):
    interview_id, resume_id, _state, primary_limit, overall_limit, asked_count = interview
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT question_text, is_follow_up FROM interview_questions
               WHERE interview_id = %s ORDER BY sequence_number""",
            (interview_id,),
        )
        prior = cursor.fetchall()
    asked = [row[0] for row in prior]
    primary_count = sum(1 for row in prior if not row[1])

    question = None
    is_follow_up = False
    if evaluation and should_ask_follow_up(evaluation, asked_count, overall_limit):
        question = evaluation["follow_up_question"]
        is_follow_up = True
    elif asked_count < overall_limit and primary_count < primary_limit:
        try:
            question = generate_session_question(
                resume_id=resume_id,
                user_id=user_id,
                asked_questions=asked,
            )
        except Exception:
            raise HTTPException(status_code=503, detail="Could not generate the next interview question.")

    if not question:
        _complete(connection, interview_id)
        return None

    sequence = asked_count + 1
    with connection.cursor() as cursor:
        cursor.execute(
            """INSERT INTO interview_questions
               (interview_id, sequence_number, question_text, is_follow_up)
               VALUES (%s, %s, %s, %s)""",
            (interview_id, sequence, question, is_follow_up),
        )
        cursor.execute(
            "UPDATE interview_sessions SET questions_asked = %s WHERE id = %s",
            (sequence, interview_id),
        )
    return {"sequence_number": sequence, "question": question, "is_follow_up": is_follow_up}


@router.post("/start/{resume_id}", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf)])
def start_interview(
    resume_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    connection: DatabaseConnection = Depends(get_db),
):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT upload_status FROM resumes WHERE id = %s AND user_id = %s",
            (resume_id, user["id"]),
        )
        resume = cursor.fetchone()
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found.")
    if resume[0] != "completed":
        raise HTTPException(status_code=409, detail="Resume processing is not complete.")

    interview_id = uuid.uuid4()
    try:
        first_question = generate_session_question(resume_id, user["id"], asked_questions=[])
    except Exception:
        raise HTTPException(status_code=503, detail="Could not generate an interview question.")
    with connection.cursor() as cursor:
        cursor.execute(
            """INSERT INTO interview_sessions
               (id, user_id, resume_id, status, primary_question_limit, overall_question_limit, questions_asked)
               VALUES (%s, %s, %s, 'active', %s, %s, 1)""",
            (interview_id, user["id"], resume_id, PRIMARY_QUESTION_LIMIT, OVERALL_QUESTION_LIMIT),
        )
        cursor.execute(
            """INSERT INTO interview_questions (interview_id, sequence_number, question_text)
               VALUES (%s, 1, %s)""",
            (interview_id, first_question),
        )
    connection.commit()
    return {"id": str(interview_id), "status": "active", "question": first_question,
            "sequence_number": 1, "is_follow_up": False,
            "question_limit": OVERALL_QUESTION_LIMIT}


@router.get("")
def interview_history(user: dict = Depends(get_current_user), connection: DatabaseConnection = Depends(get_db)):
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT i.id, i.resume_id, r.original_filename, i.status, i.created_at, i.completed_at
               FROM interview_sessions i
               JOIN resumes r ON r.id = i.resume_id AND r.user_id = i.user_id
               WHERE i.user_id = %s ORDER BY i.created_at DESC""",
            (user["id"],),
        )
        rows = cursor.fetchall()
    return [{"id": str(row[0]), "resume_id": str(row[1]), "resume_name": row[2],
             "status": row[3], "created_at": row[4].isoformat(),
             "completed_at": row[5].isoformat() if row[5] else None}
            for row in rows]


@router.get("/{interview_id}")
def current_interview(
    interview_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    connection: DatabaseConnection = Depends(get_db),
):
    interview = _owned_interview(connection, interview_id, user["id"])
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found.")
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT sequence_number, question_text, is_follow_up FROM interview_questions
               WHERE interview_id = %s AND candidate_answer IS NULL AND skipped = false
               ORDER BY sequence_number DESC LIMIT 1""",
            (interview_id,),
        )
        current = cursor.fetchone()
    return {"id": str(interview[0]), "status": interview[2],
            "question": ({"sequence_number": current[0], "question": current[1], "is_follow_up": current[2]}
                         if current else None),
            "summary": _summary(connection, interview_id) if interview[2] == "completed" else None}


def _record_response(interview_id, answer, skipped, user, connection):
    interview = _owned_interview(connection, interview_id, user["id"])
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found.")
    if interview[2] != "active":
        raise HTTPException(status_code=409, detail="This interview is already complete.")
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT id, question_text FROM interview_questions
               WHERE interview_id = %s AND candidate_answer IS NULL AND skipped = false
               ORDER BY sequence_number DESC LIMIT 1 FOR UPDATE""",
            (interview_id,),
        )
        current = cursor.fetchone()
    if current is None:
        raise HTTPException(status_code=409, detail="There is no unanswered question.")

    evaluation = None
    if not skipped:
        try:
            evaluation = evaluate_interview_answer(current[1], answer)
        except Exception:
            raise HTTPException(status_code=503, detail="Answer evaluation is temporarily unavailable.")
    with connection.cursor() as cursor:
        if skipped:
            cursor.execute("UPDATE interview_questions SET skipped = true WHERE id = %s", (current[0],))
        else:
            cursor.execute(
                """UPDATE interview_questions SET candidate_answer = %s, score = %s,
                   strengths = %s, improvements = %s, feedback = %s, follow_up_question = %s
                   WHERE id = %s""",
                     (answer, evaluation["score"], Json(evaluation["strengths"]), Json(evaluation["improvements"]),
                 evaluation["feedback"], evaluation["follow_up_question"], current[0]),
            )

    next_question = _create_next_question(connection, interview, user["id"], evaluation)
    connection.commit()
    return {"evaluation": evaluation, "next_question": next_question,
            "status": "active" if next_question else "completed",
            "summary": None if next_question else _summary(connection, interview_id)}


@router.post("/{interview_id}/answers", dependencies=[Depends(require_csrf)])
def submit_answer(
    interview_id: uuid.UUID,
    payload: AnswerSubmission,
    user: dict = Depends(get_current_user),
    connection: DatabaseConnection = Depends(get_db),
):
    return _record_response(interview_id, payload.answer.strip(), False, user, connection)


@router.post("/{interview_id}/skip", dependencies=[Depends(require_csrf)])
def skip_question(
    interview_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    connection: DatabaseConnection = Depends(get_db),
):
    return _record_response(interview_id, None, True, user, connection)


@router.post("/{interview_id}/end", dependencies=[Depends(require_csrf)])
def end_interview(
    interview_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    connection: DatabaseConnection = Depends(get_db),
):
    interview = _owned_interview(connection, interview_id, user["id"])
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found.")
    _complete(connection, interview_id)
    connection.commit()
    return {"id": str(interview_id), "status": "completed", "summary": _summary(connection, interview_id)}


@router.get("/{interview_id}/results")
def interview_results(
    interview_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    connection: DatabaseConnection = Depends(get_db),
):
    interview = _owned_interview(connection, interview_id, user["id"])
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found.")
    return {"id": str(interview_id), "status": interview[2], **_summary(connection, interview_id)}