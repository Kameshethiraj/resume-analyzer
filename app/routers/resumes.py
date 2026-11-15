import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from psycopg2.extensions import connection as DatabaseConnection

from app.auth import get_current_user, require_csrf
from app.chunker import create_chunks
from app.database import get_db
from app.job_matcher import analyze_job_match
from app.pdf_parser import extract_text_from_pdf
from app.rag import embed_texts, retrieve_chunks
from app.web_schemas import JobMatchRequest

router = APIRouter(prefix="/api/resumes", tags=["resumes"])
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _owned_resume(connection, resume_id: uuid.UUID, user_id: uuid.UUID):
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT id, original_filename, stored_filename, upload_status, created_at
               FROM resumes WHERE id = %s AND user_id = %s""",
            (resume_id, user_id),
        )
        return cursor.fetchone()


def _mark_upload_failed(connection, resume_id: uuid.UUID, user_id: uuid.UUID) -> None:
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE resumes SET upload_status = 'failed' WHERE id = %s AND user_id = %s",
                (resume_id, user_id),
            )
        connection.commit()
    except Exception:
        connection.rollback()


@router.get("")
def list_resumes(user: dict = Depends(get_current_user), connection: DatabaseConnection = Depends(get_db)):
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT r.id, r.original_filename, r.upload_status, r.created_at,
                      count(c.id) AS chunk_count
               FROM resumes r LEFT JOIN resume_chunks c ON c.resume_id = r.id
               WHERE r.user_id = %s
               GROUP BY r.id ORDER BY r.created_at DESC""",
            (user["id"],),
        )
        rows = cursor.fetchall()
    return [
        {"id": str(row[0]), "original_filename": row[1], "upload_status": row[2],
         "created_at": row[3].isoformat(), "chunk_count": row[4]}
        for row in rows
    ]


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_csrf)])
async def upload_resume(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    connection: DatabaseConnection = Depends(get_db),
):
    if Path(file.filename or "").suffix.lower() != ".pdf":
        raise HTTPException(status_code=415, detail="Upload a PDF file.")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="PDF must be 10 MB or smaller.")
    if not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="The uploaded file is not a valid PDF.")

    resume_id = uuid.uuid4()
    stored_filename = f"{resume_id}.pdf"
    storage_dir = Path(os.getenv("RESUME_STORAGE_DIR", "resume/uploads")).resolve()
    storage_dir.mkdir(parents=True, exist_ok=True)
    stored_path = storage_dir / stored_filename
    stored_path.write_bytes(content)
    original_filename = Path(file.filename or "resume.pdf").name[:255]
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO resumes (id, user_id, original_filename, stored_filename, upload_status)
                   VALUES (%s, %s, %s, %s, 'processing')""",
                (resume_id, user["id"], original_filename, stored_filename),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        stored_path.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail="Resume could not be saved.")

    try:
        text = extract_text_from_pdf(str(stored_path)).strip()
    except Exception:
        _mark_upload_failed(connection, resume_id, user["id"])
        raise HTTPException(status_code=422, detail="The PDF could not be read.")
    if not text:
        _mark_upload_failed(connection, resume_id, user["id"])
        raise HTTPException(status_code=422, detail="No readable text was found in the PDF.")

    try:
        chunks = create_chunks(text)
        embeddings = embed_texts(chunks)
    except Exception:
        _mark_upload_failed(connection, resume_id, user["id"])
        raise HTTPException(status_code=503, detail="Resume embedding is temporarily unavailable.")

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE resumes SET resume_text = %s WHERE id = %s AND user_id = %s",
                (text, resume_id, user["id"]),
            )
            for index, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                cursor.execute(
                    """INSERT INTO resume_chunks (resume_id, chunk_text, embedding, chunk_index)
                       VALUES (%s, %s, %s, %s)""",
                    (resume_id, chunk, embedding, index),
                )
            cursor.execute(
                "UPDATE resumes SET upload_status = 'completed' WHERE id = %s AND user_id = %s",
                (resume_id, user["id"]),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        _mark_upload_failed(connection, resume_id, user["id"])
        raise HTTPException(status_code=503, detail="Resume data could not be stored.")
    return {"id": str(resume_id), "original_filename": original_filename, "upload_status": "completed"}


@router.get("/{resume_id}")
def resume_details(
    resume_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    connection: DatabaseConnection = Depends(get_db),
):
    row = _owned_resume(connection, resume_id, user["id"])
    if row is None:
        raise HTTPException(status_code=404, detail="Resume not found.")
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM resume_chunks WHERE resume_id = %s", (resume_id,))
        chunk_count = cursor.fetchone()[0]
    return {"id": str(row[0]), "original_filename": row[1], "upload_status": row[3],
            "created_at": row[4].isoformat(), "chunk_count": chunk_count}


@router.get("/{resume_id}/download")
def download_resume(
    resume_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    connection: DatabaseConnection = Depends(get_db),
):
    row = _owned_resume(connection, resume_id, user["id"])
    if row is None:
        raise HTTPException(status_code=404, detail="Resume not found.")
    storage_dir = Path(os.getenv("RESUME_STORAGE_DIR", "resume/uploads")).resolve()
    path = storage_dir / row[2]
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Resume file is unavailable.")
    return FileResponse(path, media_type="application/pdf", filename=row[1])


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_csrf)])
def delete_resume(
    resume_id: uuid.UUID,
    user: dict = Depends(get_current_user),
    connection: DatabaseConnection = Depends(get_db),
):
    row = _owned_resume(connection, resume_id, user["id"])
    if row is None:
        raise HTTPException(status_code=404, detail="Resume not found.")
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM resumes WHERE id = %s AND user_id = %s", (resume_id, user["id"]))
    connection.commit()
    path = Path(os.getenv("RESUME_STORAGE_DIR", "resume/uploads")).resolve() / row[2]
    path.unlink(missing_ok=True)


@router.post("/{resume_id}/job-match", dependencies=[Depends(require_csrf)])
def job_match(
    resume_id: uuid.UUID,
    payload: JobMatchRequest,
    user: dict = Depends(get_current_user),
    connection: DatabaseConnection = Depends(get_db),
):
    row = _owned_resume(connection, resume_id, user["id"])
    if row is None:
        raise HTTPException(status_code=404, detail="Resume not found.")
    if row[3] != "completed":
        raise HTTPException(status_code=409, detail="Resume processing is not complete.")
    try:
        chunks = retrieve_chunks(payload.job_description, resume_id, user["id"], top_k=8)
        result = analyze_job_match(payload.job_description, "\n\n".join(chunks))
    except Exception:
        raise HTTPException(status_code=503, detail="Job matching is temporarily unavailable.")
    return result