import os

import psycopg2
from dotenv import load_dotenv
from pgvector.psycopg2 import register_vector
from sentence_transformers import SentenceTransformer

from app.pdf_parser import extract_text_from_pdf
from app.chunker import create_chunks


load_dotenv()


# -----------------------------
# 1. Load embedding model
# -----------------------------

model = SentenceTransformer("all-MiniLM-L6-v2")


# -----------------------------
# 2. Extract resume text
# -----------------------------

pdf_path = "resume/resume.pdf"

resume_text = extract_text_from_pdf(pdf_path)


# -----------------------------
# 3. Create chunks
# -----------------------------

chunks = create_chunks(
    resume_text,
    chunk_size=500,
    overlap=100
)

print("Number of chunks:", len(chunks))


# -----------------------------
# 4. Generate embeddings
# -----------------------------

embeddings = model.encode(chunks)

print("Embedding dimensions:", len(embeddings[0]))


# -----------------------------
# 5. Connect to PostgreSQL
# -----------------------------

connection = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD")
)

register_vector(connection)

cursor = connection.cursor()


# -----------------------------
# 6. Insert chunks + vectors
# -----------------------------

for chunk, embedding in zip(chunks, embeddings):

    cursor.execute(
        """
        INSERT INTO resume_chunks
            (resume_id, chunk_text, embedding)
        VALUES
            (%s, %s, %s)
        """,
        (
            1,
            chunk,
            embedding
        )
    )


# -----------------------------
# 7. Save changes
# -----------------------------

connection.commit()

cursor.close()
connection.close()


print("Successfully stored embeddings in PostgreSQL!")