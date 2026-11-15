import json
import ollama


def analyze_job_match(
    job_description: str,
    resume_context: str
) -> dict:

    prompt = f"""
You are a resume-job matching assistant.

Compare the job description with the resume context.

IMPORTANT RULES:
- Use ONLY information present in the resume context.
- Never invent skills or experience.
- Return ONLY valid JSON.
- Do not include markdown.
- Do not calculate a match score.

Return exactly this structure:

{{
    "required_skills": {{
        "matched": [],
        "missing": []
    }},
    "preferred_skills": {{
        "matched": [],
        "missing": []
    }},
    "experience": {{
        "required_years": null,
        "candidate_years": null
    }},
    "responsibilities_match": [],
    "skill_gaps": []
}}

JOB DESCRIPTION:
----------------
{job_description}
----------------

RESUME CONTEXT:
----------------
{resume_context}
----------------
"""

    response = ollama.chat(
        model="qwen3:4b",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        format="json",
        think=False,
        options={
            "temperature": 0,
            "num_predict": 500
        }
    )
    content = response["message"]["content"]

    print("\n========== RAW LLM RESPONSE ==========\n")
    print(repr(content))
    return json.loads(content)