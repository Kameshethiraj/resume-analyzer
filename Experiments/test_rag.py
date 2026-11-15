from app.rag import retrieve_chunks, build_context, generate_answer


question = input("Ask a question about the resume: ")

# Retrieval
chunks = retrieve_chunks(question)

print("\n========== RETRIEVED CHUNKS ==========\n")

for i, chunk in enumerate(chunks, start=1):
    print(f"--- Chunk {i} ---")
    print(chunk)
    print()


# Augmentation
context = build_context(chunks)

print("\n========== CONTEXT ==========\n")
print(context)


# Generation
answer = generate_answer(question, context)

print("\n========== ANSWER ==========\n")
print(answer)