
from app.interviewer import generate_interview_question


if __name__ == "__main__":
    question = generate_interview_question(
        resume_id=1,
        topic="backend development and project experience",
    )

    print("\n========== INTERVIEW QUESTION ==========\n")
    print(question)
