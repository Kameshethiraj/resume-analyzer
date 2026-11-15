from pydantic import BaseModel


class ResumeAnalysis(BaseModel):
    name: str | None
    summary: str
    skills: list[str]
    experience_years: float | None
    strengths: list[str]
    projects: list[str]

class SkillMatch(BaseModel):
    matched: list[str]
    missing: list[str]


class ExperienceMatch(BaseModel):
    required_years: float | None
    candidate_years: float | None


class JobMatchResult(BaseModel):
    required_skills: SkillMatch
    preferred_skills: SkillMatch
    experience: ExperienceMatch
    responsibilities_match: list[str]
    skill_gaps: list[str]