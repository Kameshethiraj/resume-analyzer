# Resume Studio Project File Guide

This is a quick map of the files that matter when running, changing, or testing the Resume Studio web application. It distinguishes files imported by the active FastAPI app from experiments and older utilities.

## Start here: the runtime path

Start the web app with `uvicorn app.main:app --reload`. Uvicorn imports the `app` object from `app/main.py`. The app registers the authentication, resume, and interview routers and serves the browser files from `app/static/`.

Typical request paths:

```text
Browser: app/static/app.js
  -> FastAPI app: app/main.py
    -> Router: app/routers/auth.py, resumes.py, or interviews.py
      -> Auth/database: app/auth.py and app/database.py
      -> Feature logic: app/interview_session.py, interviewer.py, evaluator.py,
         pdf_parser.py, chunker.py, rag.py, or job_matcher.py
      -> PostgreSQL/pgvector, local files, or local Ollama model
```

## Active web application files

### App startup and browser UI

| File | What it does |
|---|---|
| `app/main.py` | FastAPI entry point. Configures signed browser sessions, request IDs, per-login-session rotating logs, API routers, static file serving, and the `/` home page. |
| `app/static/index.html` | The single HTML shell loaded by the browser. |
| `app/static/app.css` | Responsive styling for login, dashboard, resume details, interviews, and results. |
| `app/static/app.js` | Browser behavior. Calls real API endpoints, handles the CSRF header, and renders login/register, resumes, interview questions, feedback, and results. |

### API routers

| File | Main responsibilities |
|---|---|
| `app/routers/auth.py` | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`, and `POST /api/auth/logout`. |
| `app/routers/resumes.py` | `GET/POST /api/resumes`, resume detail/download/delete, PDF processing, and the backend job-match endpoint. It checks resume ownership before private operations. |
| `app/routers/interviews.py` | Starts interviews, returns current questions/history/results, saves answers and evaluations, skips questions, and ends interviews. It checks interview ownership and limits follow-ups. |

### Authentication and database support

| File | What it does |
|---|---|
| `app/auth.py` | Reads the account identity from the signed session, confirms the user exists, assigns a login-session ID, and checks CSRF tokens. The frontend does not decide the owner ID. |
| `app/security.py` | Hashes and verifies passwords with Argon2. Plaintext passwords are not stored. |
| `app/database.py` | Loads `.env`, connects to PostgreSQL using `DATABASE_URL` or `DB_*` variables, registers UUID/vector adapters, and provides the FastAPI connection dependency. |
| `app/web_schemas.py` | Pydantic request validation models for credentials, answers, and job-match requests. |

### Resume and AI logic

| File | What it does |
|---|---|
| `app/pdf_parser.py` | Uses pypdf to extract selectable text from PDF pages. It does not OCR scanned images. |
| `app/chunker.py` | Splits extracted text into overlapping pieces. Defaults are 500 characters per chunk and 100 characters of overlap. |
| `app/rag.py` | Loads `all-MiniLM-L6-v2` lazily, creates embeddings, performs owner-scoped pgvector retrieval, joins retrieved chunks into context, and contains a local Ollama answer helper. |
| `app/interviewer.py` | Uses retrieved resume context and Ollama `qwen3:4b` to generate a distinct, resume-grounded interview question. |
| `app/evaluator.py` | Sends the question and answer to Ollama and validates the structured score, strengths, improvements, feedback, and follow-up question. |
| `app/interview_session.py` | Adapts interviewer/evaluator functions for API use without terminal `input()` or print-driven interaction. Defines the score threshold helper. |
| `app/job_matcher.py` | Compares a job description with retrieved resume context using Ollama. The API exists, though the current UI does not expose a job-match form. |

## Database and configuration files

| File | Purpose |
|---|---|
| `migrations/001_initial.sql` | Creates the pgvector extension, users, resumes, chunks, interview sessions, questions, foreign keys, and indexes. It preserves the old integer-keyed chunks table as `resume_chunks_legacy` when detected. |
| `app/migrate.py` | Reads and executes the initial SQL migration against the configured PostgreSQL database. |
| `.env.example` | Safe template for database URL, session secret, cookie setting, file storage path, and interview question limit. Copy it to `.env` and replace placeholders. Do not commit `.env`. |
| `requirements.txt` | Python package dependencies for the web app, PostgreSQL/pgvector integration, local AI clients, PDF parsing, and tests. |
| `.gitignore` | Excludes virtual environments, secrets, uploaded files, logs, and generated caches from source control. |
| `README.md` | Setup instructions and the detailed technical walkthrough. |

Resume uploads are stored on disk under `RESUME_STORAGE_DIR` (default `resume/uploads/`) using generated UUID filenames. PostgreSQL stores resume metadata and extracted/chunked text; `resume_chunks.embedding` stores vectors. A resume is not stored as a PostgreSQL binary PDF object.

## Tests versus experiments

### Automated test suite

- `tests/test_web_workflows.py`: mocked tests for password hashing/login, identity from session, owner-scoped queries, unique upload IDs, interview progression and caps, and session error logging.
- `pytest.ini`: sets `testpaths = tests`, so `python -m pytest` runs the automated suite and does not import interactive experiments.

The tests mock the database and AI calls. They validate application decisions but are not a live PostgreSQL/Ollama end-to-end test.

### Manual experiments

The Python files under `Experiments/` are learning or prototype scripts. They are not imported by `app/main.py` and are not used by the running Resume Studio web application.

| Learning script(s) | Topic |
|---|---|
| `Experiments/selfattention.py` | A small NumPy demonstration of query, key, and value matrices, scaled attention scores, softmax weights, and the weighted output. |
| `Experiments/tokenization.py` | Demonstrates splitting text into token IDs with `tiktoken` and decoding those IDs. |
| `Experiments/embeddings.py`, `generate_embeddings.py`, `local_embeddings.py`, `real_embeddings.py` | Experiments with generating text embeddings and comparing local/model-based embedding workflows. |
| `Experiments/store_embeddings.py` | Prototype for extracting/chunking a resume, generating embeddings, and inserting them directly into PostgreSQL. It predates the authenticated upload route and uses a fixed resume ID; do not use it for current multi-user data. |
| `Experiments/search.py`, `test_retrieval.py`, `test_rag.py`, `test_job_match.py` | Direct retrieval, RAG, or job-match experiments. Some scripts ask for console input and connect to the database or model services. |
| `Experiments/test_chunking.py` | Manual chunking experiment. |
| `Experiments/test_evaluator.py`, `test_interviewer.py`, `test_ollama.py`, `test_tool_calling.py` | Manual probes of Ollama, interviewer/evaluator behavior, or tool calling. |

Although several filenames start with `test_`, these are not the automated pytest suite. `pytest.ini` sets `testpaths = tests`, so `python -m pytest` collects `tests/test_web_workflows.py` instead. Some experiment scripts execute immediately, prompt for input, or call external/local services when run; inspect them before executing.

## Legacy or not currently wired into the web UI

| File/item | Current status |
|---|---|
| `app/llm.py` | Contains an older OpenAI-based resume-analysis function. It is not imported by `app/main.py` or the active resume/interview routes. The current web interview and job-match paths use local Ollama. |
| `app/schemas.py` | Pydantic models used by the legacy `app/llm.py` helper; not used by the active API routers. Active request models are in `app/web_schemas.py`. |
| `app/scorer.py` | A standalone job-match scoring formula. It is not imported by the active web app, so the current job-match endpoint does not use this score. |
| `app/tools.py` | A learning/prototype tool registry with hardcoded candidate experience, projects, and skills. It is not imported by the active web app and does not query the current user's database records. |
| `interview_results.json` | Legacy command-line interview output. The web app stores current interviews in PostgreSQL tables `interview_sessions` and `interview_questions`; it does not update this JSON file. |

## Quick change map

- Change routes or HTTP behavior: edit the relevant file in `app/routers/`.
- Change login/session/CSRF behavior: inspect `app/auth.py`, `app/security.py`, and session setup in `app/main.py`.
- Change resume parsing or chunk size: inspect `app/pdf_parser.py`, `app/chunker.py`, and the upload route in `app/routers/resumes.py`.
- Change vector retrieval or embedding model: inspect `app/rag.py` and `migrations/001_initial.sql`.
- Change interview prompts, evaluation schema, threshold, or limits: inspect `app/interviewer.py`, `app/evaluator.py`, `app/interview_session.py`, and `app/routers/interviews.py`.
- Change browser layout or interactions: edit `app/static/app.css` or `app/static/app.js`.
- Change persistent schema: add a migration under `migrations/` and update `app/migrate.py` if a new migration runner is needed.
- Add automated coverage: add tests under `tests/`, not `Experiments/`.
