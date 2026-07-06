# Pipeline

This project has two pipelines: the user-facing lecture pipeline inside the app, and the GitHub Actions pipeline that checks the code.

## Lecture Processing Pipeline

```text
Browser
  -> FastAPI
  -> upload or recording save
  -> background job
  -> transcription
  -> summary/study generation
  -> SQLite records
  -> files in outputs/
  -> dashboard, quiz, flashcards, mind map, Ask, export
```

## Step By Step

1. The browser sends a recording, uploaded media file, or text transcript to FastAPI.
2. FastAPI validates the user session, CSRF token, file type, and upload size.
3. The file is saved under `data/uploads/`.
4. A persisted job record is written to SQLite so progress survives page refreshes.
5. Audio/video files are transcribed with `faster-whisper`.
6. Text is passed into the summarisation layer.
7. The app tries local Ollama generation first when configured, then uses local fallback logic where needed.
8. Generated transcripts, summaries, combined notes, and PDFs are written under `outputs/`.
9. The dashboard reads from SQLite and exposes study tools for the signed-in user only.

## Main Modules

- `main.py`: FastAPI routes, auth checks, upload handling, background job orchestration.
- `db.py`: SQLite schema, migrations, sessions, jobs, notes, flashcards, quizzes, mind maps.
- `transcriber.py`: audio/video transcription.
- `summariser.py`: local/AI note generation.
- `study_intelligence.py`: recommendations, weak topics, quiz support.
- `advanced_outputs.py`: mind maps, scripts, richer study outputs.
- `exporter.py`: Markdown, TXT, and PDF exports.
- `file_store.py`: output paths and saved artifacts.
- `ai_note_taker_launcher.py`: Windows one-click launcher for `dist\AI Note Taker.exe`.

## GitHub Actions Pipeline

The workflow lives in `.github/workflows/ci.yml`.

On every push and pull request it:

1. Checks out the repository.
2. Sets up Python 3.12 and Node.js.
3. Installs Python dependencies.
4. Compiles the core Python files.
5. Checks JavaScript syntax with `node --check`.
6. Runs the Python unit tests.
7. Builds the Docker image.
8. On Windows, builds and verifies the one-click launcher executable.

## Release Notes

The generated `dist/` folder is ignored by Git. Build artifacts should be produced by CI or built locally with `build.bat`, then attached to a GitHub Release if you want users to download the Windows executable.

