from app.pdf_parser import extract_text_from_pdf
from app.chunker import create_chunks


pdf_path = "resume/resume.pdf"

resume_text = extract_text_from_pdf(pdf_path)

chunks = create_chunks(
    resume_text,
    chunk_size=500,
    overlap=100
)

print(f"Total chunks: {len(chunks)}")

for i, chunk in enumerate(chunks):
    print(f"\n========== CHUNK {i + 1} ==========")
    print(chunk)