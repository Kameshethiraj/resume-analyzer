from app.interviewer import generate_interview_question
from app.evaluator import evaluate_answer

FOLLOW_UP_THRESHOLD = 6


PRIMARY_QUESTION_LIMIT = 5


def generate_session_question(resume_id, user_id, asked_questions: list[str]) -> str:
    return generate_interview_question(
        resume_id=resume_id,
        user_id=user_id,
        asked_questions=asked_questions,
    )


def evaluate_interview_answer(question: str, answer: str) -> dict:
    return evaluate_answer(question, answer)


def should_ask_follow_up(evaluation: dict, questions_asked: int, overall_limit: int) -> bool:
    return evaluation["score"] < FOLLOW_UP_THRESHOLD and questions_asked < overall_limit