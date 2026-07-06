# AI Note Taker

A local-first AI lecture note-taking app for students. It records or uploads lectures, transcribes audio/video with faster-whisper, generates study notes with Ollama or local fallbacks, and exports clean PDF/Markdown/TXT outputs. It includes accounts, per-user ownership, persistent job status, upload hardening, health checks, Docker, CI, deployment docs, and a Windows one-click launcher.

## Docs

- [How to use the app](docs/USAGE.md)
- [Processing and CI pipeline](docs/PIPELINE.md)
- [Deployment guide](DEPLOYMENT.md)
- [Security audit notes](SECURITY_AUDIT.md)

## Architecture

```text
Browser UI
  | cookies + CSRF
FastAPI app
  |-- auth/session middleware
  |-- in-process job worker
  |-- SQLite data/notes.db
  |-- local files outputs/
  |-- Ollama / local summariser fallback
```

SQLite remains the default because this app is a single-node MVP with local files and one worker. The code keeps SQL parameterized and migration-safe, and `DATABASE_URL` documents the intended Postgres move for a later multi-user hosted version.

## Five-Minute Quickstart

```powershell
.\setup.ps1
.\venv\Scripts\python.exe migrate_legacy.py
.\start.ps1
```

Open `http://localhost:8000`, create the first account, and existing local lectures will be assigned to that account. To use Docker instead:

On Windows, you can also build a clickable launcher:

```powershell
.\build.bat
```

Then run `dist\AI Note Taker.exe`. It starts the app on `http://127.0.0.1:8000` and opens the browser. If the app is already running, clicking it again only opens the browser.

```powershell
Copy-Item .env.example .env
docker compose up --build
```

## Environment

Copy `.env.example` to `.env` for Docker or set the variables in your shell. Important settings:

- `APP_SECRET_KEY`: required to be changed for production.
- `APP_ENV`: set to `production` on a server.
- `MAX_UPLOAD_MB`: server-side upload limit.
- `RATE_LIMIT_AUTH_PER_MINUTE` and `RATE_LIMIT_AI_PER_MINUTE`: basic abuse protection.
- `ALLOW_DEV_PASSWORD_RESET`: local reset endpoint; turn off in production until email reset is wired.
- `OLLAMA_URL` and `OLLAMA_MODEL`: local AI generation endpoint/model.

## Data

Persistent data is stored in `data/notes.db`. Generated readable files are stored in:

```text
outputs/transcripts
outputs/summaries
outputs/pdfs
outputs/combined
```

Run a backup and schema migration with:

```powershell
.\venv\Scripts\python.exe migrate_legacy.py
```

Assign old unowned lectures to a specific existing account:

```powershell
.\venv\Scripts\python.exe migrate_legacy.py --assign-to student@example.com
```

## Features

- Record from the microphone with local recovery if the tab crashes.
- Upload audio, video, or plain text transcripts.
- Background transcription and generation with persisted job status.
- Dashboard search/filtering and study recommendations.
- Lecture tabs: overview, transcript, summary, key points, mind map, Ask, flashcards, quiz, scripts, export.
- Grounded Q&A with citation chips, scored quizzes, weak-topic review, flashcards, video/podcast scripts.
- PDF, Markdown, and TXT export.
- Email/password accounts, logout, dev-mode password reset, and per-user lecture ownership.

## Tests

```powershell
.\venv\Scripts\python.exe -m py_compile config.py security.py db.py main.py migrate_legacy.py
node --check static\app.js
.\venv\Scripts\python.exe -m unittest discover
.\venv\Scripts\python.exe -m pip_audit
```

GitHub Actions runs the compile check, JavaScript syntax check, unit tests, Docker build, and Windows launcher build on push and pull request. See [docs/PIPELINE.md](docs/PIPELINE.md).

See `SECURITY_AUDIT.md` for the current dependency audit finding and mitigation.

Manual QA checklist:

1. Create account A and upload a small `.txt` lecture.
2. Navigate away during processing, return to the dashboard, and confirm the job completes.
3. Create account B and try account A's lecture URL directly; it should return not found.
4. Log back into account A, export Markdown/PDF/TXT, and compare quality with pre-Phase 4 exports.
5. Run `migrate_legacy.py` against a copy of an older `data/notes.db` and confirm old lectures render after the first account claims them.

## Deployment

See `DEPLOYMENT.md` for the supported path: one low-cost VPS running Docker Compose with mounted `data/` and `outputs/` volumes, HTTPS handled by a reverse proxy, and secrets in `.env`.
