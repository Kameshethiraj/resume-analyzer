# from app.rag import retrieve_chunks


# question = input("Ask a question about the resume: ")

# chunks = retrieve_chunks(question)


# print("\nRetrieved chunks:\n")

# for i, chunk in enumerate(chunks, start=1):
#     print(f"========== Chunk {i} ==========")
#     print(chunk)
#     print()

from app.rag import retrieve_chunks, build_context


question = input("Ask a question about the resume: ")

chunks = retrieve_chunks(
    question,
    resume_id=1,
    top_k=5,
    max_distance=0.30
)

context = build_context(chunks)

print("\n========== CONTEXT ==========\n")
print(context)