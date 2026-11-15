import json
import random
import time

import ollama

from app.rag import retrieve_chunks, build_context

MODEL = "qwen3:4b"

TOPICS = [
    "backend development and project experience",
    "database design and SQL optimization",
    "API design and performance",
    "system design and scalability",
    "debugging and production issues",
    "testing and code quality",
    "message queues and asynchronous processing",
    "security and authentication",
    "AI/LLM integration and RAG",
    "deployment and DevOps",
]

QUESTION_SCHEMA = {
    "type": "object",
    "properties": {"question": {"type": "string"}},
    "required": ["question"],
}


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def generate_interview_question(
    resume_id,
    user_id,
    topic: str | None = None,
    asked_questions: list[str] | None = None,
) -> str:
    """Generate one varied, resume-grounded question. Raises RuntimeError on failure."""
    asked_questions = asked_questions or []
    topic = topic or random.choice(TOPICS)

    # Retrieve more chunks than needed, then sample for variety
    chunks = retrieve_chunks(
        question=f"Candidate skills, experience, and projects related to {topic}",
        resume_id=resume_id,
        user_id=user_id,
        top_k=6,
    )
    if not chunks:
        raise RuntimeError("No relevant resume content found.")

    chunks = random.sample(chunks, k=min(3, len(chunks)))
    context = build_context(chunks)

    avoid = ""
    if asked_questions:
        previous = "\n".join(f"- {q}" for q in asked_questions[-8:])
        avoid = f"\nAlready asked (do NOT repeat or rephrase these):\n{previous}\n"

    prompt = f"""
Generate exactly ONE technical interview question.

Use only the supplied resume context.
Focus on a specific skill or project mentioned in the context.
Ask about how/why/trade-offs, not just definitions.
Do not summarize the resume.
Do not answer the question.

Topic: {topic}
{avoid}
Resume context:
{context}
"""

    last_error = None
    for _ in range(3):
        try:
            response = ollama.chat(
                model=MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a technical interviewer. Generate one "
                            "concise question grounded in the supplied resume. "
                            "Return it in the required JSON format."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                format=QUESTION_SCHEMA,
                think=False,
                options={"temperature": 0.8, "num_predict": 200},
            )

            if response.get("done_reason") == "length":
                raise ValueError("Output truncated")

            question = json.loads(response["message"]["content"])["question"].strip()
            if not question:
                raise ValueError("Empty question")

            if _normalize(question) in {_normalize(q) for q in asked_questions}:
                raise ValueError("Duplicate question")

            return question

        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            last_error = error

    raise RuntimeError(f"Could not generate a valid question: {last_error}")