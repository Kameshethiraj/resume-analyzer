import json

from app.evaluator import evaluate_answer  # adjust path if evaluator.py lives elsewhere

question = (
    "Why use RabbitMQ in a food ordering platform, "
    "and how would you handle a failed message?"
)

answer = (
    "RabbitMQ processes orders asynchronously. "
    "We can retry failed messages and use a dead-letter "
    "queue for messages that repeatedly fail."
)

result = evaluate_answer(question, answer)

print("\n========== EVALUATION ==========\n")
print(json.dumps(result, indent=2))