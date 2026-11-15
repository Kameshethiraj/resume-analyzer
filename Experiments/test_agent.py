
import json
import ollama

from app.tools import TOOL_REGISTRY
from Experiments.test_tool_calling import tools


MODEL = "qwen3:4b"
MAX_STEPS = 5


def execute_tool(tool_call):
    """Validate and execute one requested tool."""

    function_name = tool_call["function"]["name"]
    arguments = tool_call["function"]["arguments"]

    print(f"\n[Agent] Selected tool: {function_name}")
    print(f"[Agent] Arguments: {arguments}")

    function = TOOL_REGISTRY.get(function_name)

    if function is None:
        return {"error": f"Unknown tool: {function_name}"}

    if not isinstance(arguments, dict):
        return {"error": "Tool arguments must be a JSON object"}

    try:
        result = function(**arguments)
        return {"result": result}
    except Exception as exc:
        return {"error": f"Tool execution failed: {exc}"}


def run_agent(user_request: str, user_id: int):
    """Run the agent until it finishes or reaches the step limit."""

    messages = [
        {
            "role": "system",
            "content": (
                "You are a backend interview preparation agent. "
                "Use available tools when you need candidate information. "
                "Inspect tool results before deciding what to do next. "
                "You may call multiple tools or make further tool calls "
                "if needed. Give a useful final answer based on the "
                "available evidence. Never invent missing candidate data."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Candidate user ID: {user_id}\n"
                f"Task: {user_request}"
            ),
        },
    ]

    for step in range(1, MAX_STEPS + 1):
        print(f"\n========== AGENT STEP {step} ==========")

        response = ollama.chat(
            model=MODEL,
            messages=messages,
            tools=tools,
            think=False,
        )

        assistant_message = response["message"]
        tool_calls = assistant_message.get("tool_calls") or []

        # No tool calls means the agent has produced its final response.
        if not tool_calls:
            print("\n========== FINAL ANSWER ==========\n")
            return assistant_message.get("content", "")

        # Preserve the assistant's tool-call message in the conversation.
        messages.append(assistant_message)

        # Execute each requested tool and feed its result back to the LLM.
        for tool_call in tool_calls:
            result = execute_tool(tool_call)

            print(f"[Agent] Tool result: {result}")

            messages.append(
                {
                    "role": "tool",
                    "content": json.dumps(result, default=str),
                }
            )

    return (
        "The agent reached its step limit before producing a final answer. "
        "Please try a simpler request."
    )


if __name__ == "__main__":
    request = (
        "Review my technical skills and projects. "
        "Tell me what I should improve for a backend engineering interview."
    )

    answer = run_agent(
        user_request=request,
        user_id=101,
    )

    print(answer)
