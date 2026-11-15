from app.pdf_parser import extract_text_from_pdf
from app.chunker import create_chunks

import os
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


# 1. Extract resume text
pdf_path = "resume/resume.pdf"

resume_text = extract_text_from_pdf(pdf_path)


# 2. Create chunks
chunks = create_chunks(
    resume_text,
    chunk_size=500,
    overlap=100
)

print("Number of chunks:", len(chunks))


# 3. Generate embedding for each chunk
for i, chunk in enumerate(chunks):

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=chunk
    )

    embedding = response.data[0].embedding

    print(f"\nChunk {i + 1}")
    print("Text:", chunk[:100])
    print("Embedding dimensions:", len(embedding))
    print("First 5 values:", embedding[:5])