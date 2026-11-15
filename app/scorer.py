def calculate_job_match_score(match: dict) -> dict:

    # -------------------------
    # Required skills: 40 points
    # -------------------------

    required_matched = len(
        match["required_skills"]["matched"]
    )

    required_missing = len(
        match["required_skills"]["missing"]
    )

    total_required = required_matched + required_missing

    if total_required > 0:
        required_score = (
            required_matched / total_required
        ) * 40
    else:
        required_score = 0


    # -------------------------
    # Experience: 20 points
    # -------------------------

    required_years = match["experience"]["required_years"]
    candidate_years = match["experience"]["candidate_years"]

    if required_years is None or candidate_years is None:
        experience_score = 0
    elif candidate_years >= required_years:
        experience_score = 20
    else:
        experience_score = (
            candidate_years / required_years
        ) * 20


    # -------------------------
    # Responsibilities: 20 points
    # -------------------------

    responsibilities = match["responsibilities_match"]

    responsibility_score = min(
        len(responsibilities) * 5,
        20
    )


    # -------------------------
    # Preferred skills: 10 points
    # -------------------------

    preferred_matched = len(
        match["preferred_skills"]["matched"]
    )

    preferred_missing = len(
        match["preferred_skills"]["missing"]
    )

    total_preferred = (
        preferred_matched + preferred_missing
    )

    if total_preferred > 0:
        preferred_score = (
            preferred_matched / total_preferred
        ) * 10
    else:
        preferred_score = 0


    # -------------------------
    # Skill gaps: 10 points
    # -------------------------

    skill_gaps = len(match["skill_gaps"])

    skill_gap_score = max(
        10 - (skill_gaps * 2),
        0
    )


    # -------------------------
    # Final score
    # -------------------------

    total_score = (
        required_score
        + experience_score
        + responsibility_score
        + preferred_score
        + skill_gap_score
    )

    return {
        "required_skills_score": round(required_score, 2),
        "experience_score": round(experience_score, 2),
        "responsibilities_score": round(
            responsibility_score, 2
        ),
        "preferred_skills_score": round(
            preferred_score, 2
        ),
        "skill_gap_score": round(
            skill_gap_score, 2
        ),
        "overall_score": round(total_score, 2)
    }