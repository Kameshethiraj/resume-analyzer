import os
from dotenv import load_dotenv
from openai import OpenAI

from app.schemas import ResumeAnalysis

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


def analyze_resume(resume_text: str) -> ResumeAnalysis:

    system_prompt = """
You are an AI resume analyzer.

Analyze the resume accurately.

Rules:
- Use only information present in the resume.
- Do not invent skills, experience, or projects.
- If information is unavailable, return null.
- Extract technical skills explicitly mentioned in the resume.
"""

    user_prompt = f"""
Analyze this resume:

{resume_text}
"""

    response = client.responses.parse(
        model="gpt-5.6-luna",
        input=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        text_format=ResumeAnalysis
    )

    return response.output_parsed


# import os
# from urllib import response

# from dotenv import load_dotenv
# from openai import OpenAI


# load_dotenv()

# client = OpenAI(
#     api_key=os.getenv("OPENAI_API_KEY")
# )


# def analyze_resume(resume_text: str) -> str:

#     prompt = f"""
# Analyze the following resume.

# Provide:
# 1. A short professional summary
# 2. Technical skills
# 3. Years of experience
# 4. Key strengths
# 5. Main projects

# Resume:

# {resume_text}
# """

#     response = client.responses.create(
#         model="gpt-5.6-luna",
#         input=prompt
#     )
#     print("Input tokens:", response.usage.input_tokens)
#     print("Output tokens:", response.usage.output_tokens)
#     print("Total tokens:", response.usage.total_tokens)

#     return response.output_text

# # if __name__ == "__main__":
# #     resume_text = """
# #     John Doe is a Software Engineer with 4 years of experience.
# #     Skills: Python, Django, PostgreSQL, Redis, RabbitMQ.
# #     Projects: Food Ordering Platform and Job Portal.
# #     """

# #     result = analyze_resume(resume_text)

# #     print(result)