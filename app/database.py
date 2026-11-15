import os
from collections.abc import Generator

import psycopg2
from dotenv import load_dotenv
from pgvector.psycopg2 import register_vector
from psycopg2.extras import register_uuid

load_dotenv()
register_uuid()


def connect(register_vectors: bool = True):
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        connection = psycopg2.connect(database_url)
    else:
        required = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            raise RuntimeError(f"Missing database configuration: {', '.join(missing)}")
        connection = psycopg2.connect(
            host=os.environ["DB_HOST"],
            port=os.getenv("DB_PORT", "5432"),
            database=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            connect_timeout=5,
        )
    if register_vectors:
        register_vector(connection)
    return connection


def get_db() -> Generator:
    connection = connect()
    try:
        yield connection
    finally:
        connection.close()