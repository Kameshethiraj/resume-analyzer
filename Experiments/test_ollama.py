
import ollama
import json

response = ollama.chat(
    model="qwen3:4b",
    messages=[
        {
            "role": "system",
            "content": (
                "You are a technical interview question generator. "
                "Return a JSON object with one key named 'question'. "
                "The value must be exactly one concise question. "
                "Do not include explanations."
            ),
        },
        {
            "role": "user",
            "content": "Topic: PostgreSQL",
        },
    ],
    format={
        "type": "object",
        "properties": {
            "question": {"type": "string"}
        },
        "required": ["question"],
    },
    think=False,
    options={
        "temperature": 0,
        "num_predict": 100,
    },
)

content = response["message"]["content"]
print("Raw response:", repr(content))

try:
    result = json.loads(content)
    print("\nInterview question:", result["question"])
except (json.JSONDecodeError, KeyError):
    print("The model did not return the expected JSON.")
