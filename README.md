# AI Resume Analyzer

A local, multi-user resume and interview application built around the existing FastAPI, PostgreSQL/pgvector, SentenceTransformers, and Ollama modules.

## Requirements

- Python 3.10 or newer
- PostgreSQL with permission to enable the `vector` extension (pgvector installed on the server)
- Ollama running locally with `qwen3:4b`

## Local setup

From the project directory, create and activate a virtual environment, then install dependencies:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `DATABASE_URL` and `SESSION_SECRET` in `.env`. Generate a session secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. For local development, `SESSION_COOKIE_SECURE=false` is suitable; set it to `true` behind HTTPS.

Create the PostgreSQL database and install the pgvector server extension if needed. Apply the initial schema migration:

```powershell
python -m app.migrate
```

The migration creates the tables and indexes. If it finds the old integer-keyed `resume_chunks` prototype table, it preserves that table as `resume_chunks_legacy`; those rows have no verified owner and are not exposed through the application.

Start Ollama and pull the configured model, then run the web server:

```powershell
ollama pull qwen3:4b
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. The embedding model `all-MiniLM-L6-v2` is loaded on the first resume upload or vector search and may download its model files on first use.

## Tests

Run the automated API/service tests with:

```powershell
python -m pytest
```

The tests mock PostgreSQL and AI calls; they exercise authentication, owner-scoped queries, upload handling, and interview progression without requiring live external services. End-to-end model and database behavior still requires a configured local PostgreSQL/pgvector instance and Ollama.

## Security and data

Browser authentication uses an eight-hour, HTTP-only, same-site session cookie with a CSRF token required for mutations. Passwords are hashed with Argon2. Resume IDs are UUIDs, and all resume/interview API reads and mutations are scoped to the authenticated user. Uploaded files are stored under generated UUID filenames in `RESUME_STORAGE_DIR`; protect and back up that directory as private application data.

Authenticated HTTP requests are logged to one rotating file per login session under `logs/user_sessions/<user-uuid>/<session-uuid>.log`. Unexpected server errors include a traceback in that user's session log. The browser shows a request reference ID for server errors; search that ID in the corresponding log. Request bodies, passwords, and interview answers are not logged. Set `APP_LOG_DIR` to move logs to a different protected directory.

## Technical walkthrough

This section explains how the documented technologies fit together in the current source code. It describes implemented behavior, not a promise that every production feature is present.

### Architecture and source map

| Component | Responsibility |
|---|---|
| `app/main.py` | Creates the FastAPI application, configures signed browser sessions and request logging, registers API routers, and serves the browser files. |
| `app/routers/auth.py` | Registers users, verifies logins, and exposes the current authenticated user and logout operations. |
| `app/routers/resumes.py` | Uploads, processes, lists, downloads, matches, and deletes resumes. Every private resume operation checks the owner. |
| `app/routers/interviews.py` | Creates interviews, serves the current question, evaluates answers, handles skips and endings, and returns history/results. |
| `app/database.py` and `migrations/001_initial.sql` | Open PostgreSQL connections and define tables, constraints, and indexes. |
| `app/interview_session.py`, `app/interviewer.py`, `app/evaluator.py` | Separate the reusable interview behavior from HTTP handling and terminal interaction. The interviewer and evaluator call Ollama. |
| `app/pdf_parser.py`, `app/chunker.py`, `app/rag.py` | Extract PDF text, split it, generate embeddings, and retrieve relevant chunks from PostgreSQL/pgvector. |
| `app/static/` | Contains the HTML, CSS, and JavaScript browser interface. The JavaScript calls the real FastAPI endpoints. |

The request path is browser to FastAPI, then authentication/ownership checks, then a router. Depending on the operation, the router talks to PostgreSQL, the local filesystem, SentenceTransformers, or Ollama. PostgreSQL and pgvector are one database service here: pgvector adds vector storage and similarity operators to PostgreSQL. Redis, RabbitMQ, a separate vector database, and background workers are not configured in this project.

### Requirements explained

- **Python 3.10 or newer:** The source uses modern type syntax such as `list[str]` and `str | None`. FastAPI runs the HTTP application; Uvicorn is the ASGI server that accepts HTTP connections and invokes it.
- **PostgreSQL and pgvector:** PostgreSQL stores users, resume metadata/text, interview sessions, questions, answers, and feedback. pgvector stores the 384-dimensional embedding for each resume chunk and provides the `<=>` distance operator used to rank chunks. The server needs pgvector installed, and the database role needs permission to create the `vector` extension during migration.
- **Ollama with `qwen3:4b`:** Ollama runs the chat model on the local machine and provides a local HTTP API. `app/interviewer.py`, `app/evaluator.py`, and `app/job_matcher.py` call it through the Python `ollama` package. The current web routes do not call OpenAI. `app/llm.py` is a separate, older OpenAI-based module and is not wired into `app/main.py` or the current resume/interview routes.
- **SentenceTransformers with `all-MiniLM-L6-v2`:** This model converts text into numerical vectors so PostgreSQL can find semantically related resume sections. `app/rag.py` loads it lazily in `get_embedding_model()` and caches the instance for reuse in that process. The first use may download weights from Hugging Face; later embedding inference is local.
- **pypdf:** `app/pdf_parser.py` uses `PdfReader` to extract selectable text page by page. It does not perform OCR, so image-only/scanned PDFs may produce no text.

### Setup and startup, step by step

1. `python -m venv .venv` creates an isolated Python environment. Activating it makes `python` and `pip` refer to this project's environment rather than a global installation.
2. `python -m pip install -r requirements.txt` installs the packages used by the app and tests. `.env.example` is a template; copy it to `.env` and replace the placeholder database URL and session secret with real local values.
3. `SESSION_SECRET` is used by Starlette's `SessionMiddleware` to sign the browser cookie. Generate a long random value. If it is omitted, `app/main.py` creates a new random value at startup, which invalidates cookies on restart and is unsuitable for multiple server workers.
4. Create the PostgreSQL database and ensure its server has pgvector installed. `python -m app.migrate` calls `app/migrate.py`, which executes `migrations/001_initial.sql`. The migration first creates the `vector` extension, then the application tables. If it sees the old integer-keyed prototype chunk table, it renames it to `resume_chunks_legacy`; old rows have no verified owner and are not queried by the web app.
5. `ollama pull qwen3:4b` downloads the local chat model. Ollama must be running when question generation, answer evaluation, or job matching is requested.
6. `uvicorn app.main:app --reload` imports the `app` object from `app/main.py`. `--reload` is a development convenience that restarts the process when watched source files change. The home route serves `app/static/index.html`; `/static` serves its JavaScript and CSS.

`app/database.py` loads `.env`, registers UUID conversion for psycopg2, reads `DATABASE_URL` or the individual `DB_*` settings, and returns a PostgreSQL connection. FastAPI's `get_db()` dependency gives a connection to the route and closes it after the request. The current design opens a connection per request rather than using a connection pool.

### Database model

| Table | What it stores and how it relates |
|---|---|
| `users` | UUID user ID, unique email, Argon2 password hash, and creation timestamp. |
| `resumes` | UUID resume ID, owner `user_id`, original display filename, generated storage filename, processing status, extracted text, and creation timestamp. |
| `resume_chunks` | Resume UUID, chunk text, chunk index, and `VECTOR(384)` embedding. A foreign key cascades when the resume is deleted. |
| `interview_sessions` | Interview UUID, owner UUID, resume UUID, active/completed status, question limits/count, and timestamps. A composite foreign key requires the resume and user to be a valid owner pair. |
| `interview_questions` | Ordered question text, whether it is a follow-up, submitted answer or skip status, score, JSONB strengths/improvements, feedback, and generated follow-up text. |

Foreign keys prevent orphaned records and `ON DELETE CASCADE` removes dependent database rows. Indexes support owner/date listings, chunk lookup by resume, and question lookup by interview. The migration does not create an HNSW or IVFFlat vector index, so similarity search may become slower as a resume accumulates many chunks.

### Resume upload and retrieval flow

The browser sends a multipart request to `POST /api/resumes`. `app/routers/resumes.py` requires an authenticated user and a CSRF token. It checks the `.pdf` suffix, reads at most 10 MB plus one byte to detect oversize uploads, and checks the PDF signature. These checks reject common mistakes; pypdf parsing is the later check that the content is actually readable as a PDF.

The server generates a UUID for every upload, even if the same user uploads the same file twice. It uses that UUID as the stored filename instead of trusting the original filename. It writes a `processing` metadata row, extracts text with `extract_text_from_pdf()`, splits text with `create_chunks()`, encodes chunks with `embed_texts()`, inserts the text and vectors, and marks the resume `completed`. The chunker uses 500-character windows with 100 characters of overlap, preserving some context across adjacent chunks. If parsing, embedding, or storage fails, the route marks the record `failed` where possible and returns an HTTP error.

This processing is synchronous: the upload request does not return until parsing and embedding finish. Although the route is declared `async`, PDF parsing, model inference, and database work are synchronous calls. Large resumes or first-time model initialization can therefore increase response latency. A background worker and job-status polling would be a better fit for larger deployments.

For a question, `retrieve_chunks()` embeds the search text and queries PostgreSQL. Its key filters are both `c.resume_id = %s` and `r.user_id = %s`; the join ensures that knowing a UUID alone does not grant access to another user's content. `<=>` ranks rows by cosine distance, and `LIMIT` bounds the number returned. The interviewer samples relevant chunks and includes them in the Ollama prompt as resume context. This is retrieval-augmented generation (RAG): retrieve source material first, then ask the language model to generate using that material.

### Interview flow

1. The browser calls `POST /api/interviews/start/{resume_id}`. The API verifies the current user's ownership and that the resume is completed, then asks Ollama for the first question and stores an `interview_sessions` row plus question number 1.
2. `GET /api/interviews/{interview_id}` returns the current unanswered question, but only after `_owned_interview()` confirms both interview ownership and the associated resume relationship.
3. The browser posts an answer to `POST /api/interviews/{interview_id}/answers`. The API locks the unanswered question row, calls `evaluate_answer()`, and stores the answer, score, strengths, improvements, feedback, and follow-up question. Psycopg2's `Json` adapter serializes the strengths/improvements lists for the JSONB columns.
4. Scores below `FOLLOW_UP_THRESHOLD = 6` use the evaluator's follow-up question, unless the overall question cap has been reached. Otherwise the API asks for another primary question, up to five primary questions. The default total cap is eight, configured by `INTERVIEW_QUESTION_LIMIT` when the app starts; the value is stored on each new interview session.
5. `POST /api/interviews/{interview_id}/skip` marks the current question skipped and advances without evaluation. `POST /api/interviews/{interview_id}/end` ends the session early. `GET /api/interviews` lists the current user's history, and `GET /api/interviews/{interview_id}/results` returns that session's answers and average score.

The main model behavior remains in `app/interviewer.py` and `app/evaluator.py`; `app/interview_session.py` provides wrappers so the same behavior can be called without terminal `input()` or print-driven control flow. The older command-line loop was replaced by HTTP requests and persisted state.

### Authentication, UI, and ownership

`POST /api/auth/register` normalizes the email and stores `hash_password(password)`, never the plaintext password. Argon2 generates a salted password hash and `verify_password()` checks it at login. `POST /api/auth/login` establishes a signed session containing the user UUID, a CSRF token, and a login-session UUID. `GET /api/auth/me` returns the current account and CSRF token; `POST /api/auth/logout` clears the cookie session.

The frontend uses the cookie automatically with same-origin `fetch()` calls. For mutations it sends the CSRF value in `X-CSRF-Token`; `require_csrf()` compares it with the session value. Every private route obtains the identity through `get_current_user()`, which checks the UUID against the users table. The frontend never chooses the owner ID. SQL values are passed as psycopg2 parameters rather than concatenated into SQL strings.

The browser is a small vanilla JavaScript application rather than a separate React/Vue project. `app/static/app.js` renders the login/register forms, dashboard, resume details, interview question, feedback, and results. It escapes server-provided strings before inserting them into HTML. The dashboard's Close session action calls the authenticated interview-end route for active interviews belonging to the resume; Delete calls the owner-checked resume deletion route, which also cascades interview/chunk records.

The backend also implements `POST /api/resumes/{resume_id}/job-match`; it retrieves owner-scoped resume chunks and calls Ollama through `analyze_job_match()`. The current browser UI does not include a job-match form. `rag.generate_answer()` is another helper that is not currently exposed as an API route.

### Tests and what they prove

Run `python -m pytest` from the project root using the project's virtual environment. `pytest.ini` limits test collection to `tests/`; scripts under `Experiments/` are manual experiments and some read from terminal input during import.

`tests/test_web_workflows.py` has eight tests for password hashing/login, session-derived identity, owner-filtered queries, unique safe upload filenames, interview answer persistence/progression, follow-up caps, and per-session error logging. The tests use fake database connections and mock model calls. They verify important route/service decisions quickly, but they do not prove behavior against a real PostgreSQL server, pgvector operators, an actual PDF/model combination, or Ollama output. Those integrations should be exercised separately when changing database or model behavior.

### Errors, logs, and practical debugging

Expected HTTP errors use statuses such as 401 for missing/invalid authentication, 403 for invalid CSRF, 404 for resources not owned or not found, 409 for invalid state, 413 for an oversized PDF, 415 for a non-PDF, 422 for unreadable content, and 503 for unavailable AI/storage operations. Unexpected exceptions return a generic 500 response rather than exposing a traceback to the browser.

For an authenticated login session, `app/main.py` writes request IDs, method, path, status, duration, and unexpected-error tracebacks to `logs/user_sessions/<user-uuid>/<session-uuid>.log`. Logs rotate at 2 MB and retain three backups. A 500 response includes a request reference; search that ID in the file to find its traceback. Request bodies, passwords, and interview answers are deliberately not logged. Unauthenticated requests have no per-user log because there is no validated user identity to associate with them.

If a request fails, first note its HTTP status and request reference, then inspect the corresponding session log. For example, a PostgreSQL error saying a column is JSONB but an expression is `text[]` points to parameter adaptation: Python lists must be sent through psycopg2's `Json` adapter for JSONB columns. If an interview fails before a database write, check that Ollama is running and that `qwen3:4b` is pulled. If upload fails during parsing, verify the PDF has selectable text; image-only PDFs need OCR, which is not implemented.

### Trade-offs and production improvements

- The current one-process local setup is easy to inspect, but each request opens a database connection. A connection pool and tested concurrency limits would be useful under load.
- Embeddings and Ollama calls run inline. A background queue could keep HTTP requests responsive, but no Redis, RabbitMQ, or worker is currently part of this project.
- Passwords use Argon2 and private endpoints scope queries by owner, but deployment should add rate limiting, account recovery, email verification, and monitoring for repeated login failures.
- Session cookies should use HTTPS in deployment, and `SESSION_SECRET` should come from a secret manager. Log and resume directories contain private data and need filesystem permissions, retention rules, and backups.
- The schema uses a hand-run SQL migration. A migration tool such as Alembic would provide ordered schema versions and controlled upgrades as the data model evolves.
- The upload limit and generated filenames reduce common upload risks, but there is no malware scanning, OCR, encrypted file storage, or automated cleanup of orphan files.