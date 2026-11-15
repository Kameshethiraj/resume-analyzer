def get_experience(user_id: int) -> int:
    """
    Get the candidate's total years of experience.
    """
    # Hardcoded for learning.
    # Later this will come from PostgreSQL.
    return 4


def get_projects(user_id: int) -> list[str]:
    """
    Get the candidate's projects.
    """
    # Hardcoded for learning.
    # Later this will come from PostgreSQL.
    return [
        "Food Ordering Platform",
        "Job Portal"
    ]


def get_skills(user_id: int) -> list[str]:
    """
    Get the candidate's technical skills.
    """
    return [
        "Python",
        "Django",
        "Django REST Framework",
        "FastAPI",
        "PostgreSQL",
        "MySQL",
        "Redis",
        "RabbitMQ",
        "Docker"
    ]


# --------------------------------
# TOOL REGISTRY
# --------------------------------

TOOL_REGISTRY = {
    "get_experience": get_experience,
    "get_projects": get_projects,
    "get_skills": get_skills,
}