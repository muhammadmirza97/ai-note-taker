# How To Use AI Note Taker

AI Note Taker is a local-first study app. You run it on your computer, open it in a browser, and use it to turn lectures, recordings, videos, or text notes into study material.

## First-Time Setup

Requirements:

- Windows, macOS, or Linux for the web app.
- Python 3.11 or newer.
- Ollama for local AI generation. The Windows setup script can install/start it for you.

On Windows:

```powershell
.\setup.ps1
```

Then start the app:

```powershell
.\start.ps1
```

Open:

```text
http://localhost:8000
```

Create your first account. If you already had local lecture records, the first account claims those older lectures.

## One-Click Windows Launcher

After building the launcher, use:

```text
dist\AI Note Taker.exe
```

Clicking the executable starts the app on `http://127.0.0.1:8000` and opens it in your browser. If the app is already running, clicking again opens the browser without starting a duplicate server.

Build the launcher with:

```powershell
.\build.bat
```

## Daily Workflow

1. Start the app with `start.ps1` or the `AI Note Taker.exe` launcher.
2. Sign in.
3. Record a lecture, upload audio/video, or upload a `.txt`/Markdown transcript.
4. Wait for the background job to finish transcription and note generation.
5. Review the lecture dashboard.
6. Use the tabs for transcript, summary, key points, flashcards, quiz, mind map, Ask, scripts, and exports.
7. Export your notes as Markdown, TXT, or PDF.

## Local Data

These files are intentionally not committed to GitHub:

```text
data/notes.db
data/uploads/
outputs/
```

Back them up if you want to keep your lectures when moving computers.

## Docker Option

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Then open `http://localhost:8000`.

For server deployment, see `DEPLOYMENT.md`.

