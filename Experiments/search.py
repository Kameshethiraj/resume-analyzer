import os

import psycopg2
from dotenv import load_dotenv
from pgvector.psycopg2 import register_vector
from sentence_transformers import SentenceTransformer

load_dotenv()


# 1. Load the same embedding model
model = SentenceTransformer("all-MiniLM-L6-v2")


# 2. Get the user's question
question = input("Ask a question about the resume: ")


# 3. Convert question into an embedding
query_embedding = model.encode(question)


# 4. Connect to PostgreSQL
connection = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    port=os.getenv("DB_PORT"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD")
)

register_vector(connection)

cursor = connection.cursor()


# 5. Find the most similar resume chunks
cursor.execute(
    """
    SELECT
        id,
        chunk_text,
        embedding <=> %s AS distance
    FROM resume_chunks
    WHERE resume_id = %s
    ORDER BY embedding <=> %s
    LIMIT 3;
    """,
    (
        query_embedding,
        1,
        query_embedding
    )
)


results = cursor.fetchall()


# 6. Display results
print("\nTop matching chunks:\n")

for rank, (chunk_id, chunk_text, distance) in enumerate(results, start=1):

    print(f"========== Result {rank} ==========")
    print(f"Chunk ID: {chunk_id}")
    print(f"Distance: {distance:.4f}")
    print(chunk_text)
    print()


cursor.close()
connection.close()