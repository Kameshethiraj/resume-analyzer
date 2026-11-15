from app.rag import retrieve_chunks, build_context
from app.job_matcher import analyze_job_match
from app.scorer import calculate_job_match_score


with open(
    "job_descriptions/backend_engineer.txt",
    "r",
    encoding="utf-8"
) as file:

    job_description = file.read()


chunks = retrieve_chunks(
    question=job_description,
    resume_id=1,
    top_k=5,
    max_distance=0.30
)


context = build_context(chunks)


match_result = analyze_job_match(
    job_description,
    context
)


score = calculate_job_match_score(
    match_result
)


print("\n========== MATCH RESULT ==========\n")
print(match_result)


print("\n========== SCORE ==========\n")
for key, value in score.items():
    print(f"{key}: {value}")