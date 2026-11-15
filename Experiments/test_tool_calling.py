import json
import ollama

from app.tools import TOOL_REGISTRY


# ============================================================
# TOOL DEFINITIONS
# ============================================================

tools = [

    {
        "type": "function",
        "function": {
            "name": "get_experience",
            "description": (
                "Get the candidate's total years "
                "of professional experience."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "The user's ID"
                    }
                },
                "required": ["user_id"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "get_projects",
            "description": (
                "Get the projects belonging to a user."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "The user's ID"
                    }
                },
                "required": ["user_id"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "get_skills",
            "description": (
                "Get the candidate's technical skills."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "integer",
                        "description": "The user's ID"
                    }
                },
                "required": ["user_id"]
            }
        }
    }
]


# ============================================================
# USER MESSAGE
# ============================================================

messages = [
    {
        "role": "user",
        "content": (
            "For user 101, tell me their years of "
            "experience, projects, and technical skills."
        )
    }
]


# ============================================================
# FIRST LLM CALL WITH TOOL DEFINITIONS
# ============================================================

response = ollama.chat(
    model="qwen3:4b",
    messages=messages,
    tools=tools,
    think=False
)


print("\n========== FIRST LLM RESPONSE ==========\n")
print(response)


# ============================================================
# CHECK FOR TOOL CALLS
# ============================================================

tool_calls = response["message"].get("tool_calls", [])

if tool_calls:

    # Add LLM's tool-call message to conversation
    messages.append(response["message"])


    # ========================================================
    # EXECUTE EACH TOOL
    # ========================================================

    for tool_call in tool_calls:

        function_name = tool_call["function"]["name"]

        arguments = tool_call["function"]["arguments"]


        print("\n========== TOOL CALL ==========\n")

        print("Function:", function_name)
        print("Arguments:", arguments)


        # ----------------------------------------------------
        # Find actual Python function
        # ----------------------------------------------------

        function = TOOL_REGISTRY.get(function_name)


        if function is None:

            result = {
                "error": f"Unknown tool: {function_name}"
            }

        else:

            # ------------------------------------------------
            # Execute Python function dynamically
            # ------------------------------------------------

            result = function(**arguments)


        print("Result:", result)


        # ====================================================
        # SEND TOOL RESULT BACK TO LLM
        # ====================================================

        messages.append(
            {
                "role": "tool",
                "content": json.dumps(result)
            }
        )


    # ========================================================
    # SECOND LLM CALL WITH TOOL RESULTS
    # ========================================================

    final_response = ollama.chat(
        model="qwen3:4b",
        messages=messages,
        tools=tools,
        think=False
    )


    print("\n========== FINAL ANSWER ==========\n")

    print(final_response["message"]["content"])


else:

    print("\n========== LLM ANSWER ==========\n")

    print(response["message"]["content"])