import ollama

from app.database import connect

_embedding_model = None


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer

        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model


def embed_texts(texts: list[str]):
    return get_embedding_model().encode(texts)


# def retrieve_chunks(
#     question: str,
#     top_k: int = 3,
#     max_distance: float | None = None
# ):

#     # Convert question into vector
#     query_embedding = embedding_model.encode(question)

#     # Connect to PostgreSQL
#     connection = psycopg2.connect(
#         host=os.getenv("DB_HOST"),
#         port=os.getenv("DB_PORT"),
#         database=os.getenv("DB_NAME"),
#         user=os.getenv("DB_USER"),
#         password=os.getenv("DB_PASSWORD")
#     )

#     register_vector(connection)

#     cursor = connection.cursor()

#     cursor.execute(
#         """
#         SELECT chunk_text
#         FROM resume_chunks
#         ORDER BY embedding <=> %s
#         LIMIT %s;
#         """,
#         (query_embedding, top_k)
#     )

#     results = cursor.fetchall()

#     cursor.close()
#     connection.close()

#     return [row[0] for row in results]

def retrieve_chunks(
    question: str,
    resume_id,
    user_id,
    top_k: int = 3,
    max_distance: float | None = None
):
    if user_id is None:
        raise ValueError("An authenticated user_id is required for resume retrieval.")
    query_embedding = embed_texts([question])[0]
    connection = connect()
    try:
        with connection.cursor() as cursor:
            if max_distance is None:
                cursor.execute(
                    """
                    SELECT c.chunk_text
                    FROM resume_chunks c
                    JOIN resumes r ON r.id = c.resume_id
                    WHERE c.resume_id = %s AND r.user_id = %s
                    ORDER BY c.embedding <=> %s
                    LIMIT %s
                    """,
                    (resume_id, user_id, query_embedding, top_k),
                )
            else:
                cursor.execute(
                    """
                    WITH ranked AS (
                        SELECT c.chunk_text, c.embedding <=> %s AS distance
                        FROM resume_chunks c
                        JOIN resumes r ON r.id = c.resume_id
                        WHERE c.resume_id = %s AND r.user_id = %s
                    )
                    SELECT chunk_text FROM ranked
                    WHERE distance <= %s ORDER BY distance LIMIT %s
                    """,
                    (query_embedding, resume_id, user_id, max_distance, top_k),
                )
            return [row[0] for row in cursor.fetchall()]
    finally:
        connection.close()

def build_context(chunks: list[str]) -> str:
    return "\n\n---\n\n".join(chunks)


def generate_answer(question: str, context: str) -> str:

    prompt = f"""
You are a resume assistant.

Answer the question using ONLY the information in the context below.

If the answer is not present in the context, say:
"I couldn't find that information in the resume."

Context:
----------------
{context}
----------------

Question:
{question}

Answer:
"""

    response = ollama.chat(
        model="qwen3:4b",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response["message"]["content"]