import json
import ollama

MODEL = "qwen3:4b"  # try "qwen3:4b-instruct-2507" for better format-following

SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 0, "maximum": 10},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "improvements": {"type": "array", "items": {"type": "string"}},
        "feedback": {"type": "string"},
        "follow_up_question": {"type": "string"},
    },
    "required": [
        "score",
        "strengths",
        "improvements",
        "feedback",
        "follow_up_question",
    ],
}

SYSTEM_PROMPT = (
    "You are an experienced backend engineering interviewer. "
    "Evaluate the candidate's answer fairly and strictly. "
    "Respond ONLY with JSON matching the required schema."
)


def build_prompt(question: str, answer: str) -> str:
    return f"""Evaluate this candidate's technical answer.

Question:
{question}

Candidate answer:
{answer}

Return JSON with these fields, in this order:
1. score: integer 0-10 based on correctness, relevance, completeness
2. strengths: 1-3 short, specific points
3. improvements: 1-3 short, actionable points
4. feedback: 2-3 sentences summarizing the evaluation
5. follow_up_question: one relevant follow-up question

Keep every string concise. Do not repeat the question or answer.
"""


def evaluate_answer(question: str, answer: str) -> dict:
    if not answer or not answer.strip():
        return {
            "score": 0,
            "strengths": [],
            "improvements": ["Provide an answer to the question."],
            "feedback": "No answer was provided.",
            "follow_up_question": question,
        }

    prompt = build_prompt(question, answer)
    last_error = None

    for attempt in range(3):
        try:
            user_content = prompt
            if attempt > 0:
                user_content += (
                    "\nYour previous response was invalid. "
                    "Return a complete, valid JSON evaluation."
                )

            response = ollama.chat(
                model=MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                format=SCHEMA,
                think=False,
                options={"temperature": 0, "num_predict": 1000},
            )

            if response.get("done_reason") == "length":
                raise ValueError("Output truncated (hit num_predict limit)")

            content = response["message"]["content"]
            result = json.loads(content)

            score = result.get("score")
            if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 10:
                raise ValueError(f"Invalid score: {score!r}")
            if not str(result.get("feedback", "")).strip():
                raise ValueError("Empty feedback")
            if not str(result.get("follow_up_question", "")).strip():
                raise ValueError("Empty follow-up question")
            if not isinstance(result.get("strengths"), list):
                raise ValueError("Invalid strengths")
            if not isinstance(result.get("improvements"), list):
                raise ValueError("Invalid improvements")

            return result

        except (json.JSONDecodeError, ValueError, TypeError) as error:
            last_error = error
            print(f"Attempt {attempt + 1} failed: {error}")

    raise RuntimeError(
        f"Could not obtain a valid evaluation after 3 attempts: {last_error}"
    )