from pydantic import BaseModel, Field


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=256)


class AnswerSubmission(BaseModel):
    answer: str = Field(max_length=12000)


class JobMatchRequest(BaseModel):
    job_description: str = Field(min_length=1, max_length=30000)