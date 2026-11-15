from pathlib import Path

from app.database import connect


def migrate() -> None:
    migration = Path(__file__).resolve().parent.parent / "migrations" / "001_initial.sql"
    connection = connect(register_vectors=False)
    try:
        with connection.cursor() as cursor:
            cursor.execute(migration.read_text(encoding="utf-8"))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    migrate()
    print("Database migration completed.")