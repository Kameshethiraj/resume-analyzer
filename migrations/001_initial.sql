CREATE EXTENSION IF NOT EXISTS vector;

DO $$
BEGIN
    IF to_regclass('public.resume_chunks') IS NOT NULL
       AND EXISTS (
           SELECT 1
           FROM pg_attribute a
           JOIN pg_class c ON c.oid = a.attrelid
           JOIN pg_type t ON t.oid = a.atttypid
           WHERE c.oid = 'public.resume_chunks'::regclass
             AND a.attname = 'resume_id'
             AND a.attnum > 0
             AND NOT a.attisdropped
             AND t.typname <> 'uuid'
       )
       AND to_regclass('public.resume_chunks_legacy') IS NULL THEN
        ALTER TABLE public.resume_chunks RENAME TO resume_chunks_legacy;
        IF to_regclass('public.resume_chunks_id_seq') IS NOT NULL
           AND to_regclass('public.resume_chunks_legacy_id_seq') IS NULL THEN
            ALTER SEQUENCE public.resume_chunks_id_seq RENAME TO resume_chunks_legacy_id_seq;
        END IF;
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS resumes (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL UNIQUE,
    upload_status TEXT NOT NULL CHECK (upload_status IN ('processing', 'completed', 'failed')),
    resume_text TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (id, user_id)
);
CREATE INDEX IF NOT EXISTS resumes_owner_created_idx ON resumes(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS resume_chunks (
    id BIGSERIAL PRIMARY KEY,
    resume_id UUID NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
    chunk_text TEXT NOT NULL,
    embedding VECTOR(384) NOT NULL,
    chunk_index INTEGER NOT NULL,
    UNIQUE (resume_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS resume_chunks_resume_idx ON resume_chunks(resume_id);

CREATE TABLE IF NOT EXISTS interview_sessions (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    resume_id UUID NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'completed')),
    primary_question_limit INTEGER NOT NULL DEFAULT 5,
    overall_question_limit INTEGER NOT NULL DEFAULT 8,
    questions_asked INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    UNIQUE (id, user_id, resume_id),
    FOREIGN KEY (resume_id, user_id) REFERENCES resumes(id, user_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS interview_sessions_owner_idx ON interview_sessions(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS interview_questions (
    id BIGSERIAL PRIMARY KEY,
    interview_id UUID NOT NULL REFERENCES interview_sessions(id) ON DELETE CASCADE,
    sequence_number INTEGER NOT NULL,
    question_text TEXT NOT NULL,
    is_follow_up BOOLEAN NOT NULL DEFAULT false,
    candidate_answer TEXT,
    skipped BOOLEAN NOT NULL DEFAULT false,
    score INTEGER CHECK (score BETWEEN 0 AND 10),
    strengths JSONB NOT NULL DEFAULT '[]'::jsonb,
    improvements JSONB NOT NULL DEFAULT '[]'::jsonb,
    feedback TEXT,
    follow_up_question TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (interview_id, sequence_number)
);
CREATE INDEX IF NOT EXISTS interview_questions_session_idx ON interview_questions(interview_id, sequence_number);