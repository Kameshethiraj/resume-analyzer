from app.pdf_parser import extract_text_from_pdf
from app.chunker import create_chunks

from sentence_transformers import SentenceTransformer


# 1. Load local embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")


# 2. Extract resume text
pdf_path = "resume/resume.pdf"

resume_text = extract_text_from_pdf(pdf_path)


# 3. Create chunks
chunks = create_chunks(
    resume_text,
    chunk_size=500,
    overlap=100
)

print("Number of chunks:", len(chunks))


# 4. Generate embeddings
embeddings = model.encode(chunks)


# 5. Verify
print("Number of embeddings:", len(embeddings))
print("Embedding dimensions:", len(embeddings[0]))

print("\nFirst chunk:")
print(chunks[0])

print("\nFirst 5 values of its embedding:")
print(embeddings[0][:5])