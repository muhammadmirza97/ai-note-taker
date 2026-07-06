# Windows Project Launcher

A friendly Windows home screen for local apps. Add each project once, then start it with one obvious button. The launcher assigns every app a stable localhost port, starts setup/run commands, waits until the server is ready, opens the browser, shows live logs, and can stop the full process tree.

Screenshot placeholder:

```text
[ Project cards with status pills, one Start/Stop button, clickable localhost URLs, and a small menu ]
```

## Run From Source

```powershell
.\venv\Scripts\python.exe -m launcher
```

On first run, the app creates an empty, clean project list:

```text
%APPDATA%\ProjectLauncher\projects.json
%APPDATA%\ProjectLauncher\launcher.log
%APPDATA%\ProjectLauncher\logs\
```

## Build The EXE

```powershell
.\build.bat
```

The portable executable is written to `dist\ProjectLauncher.exe`.

## Port System

The launcher owns ports `8100-8199` by default. Each project gets one stable port, stored in config. On start, the launcher:

- checks that the port is free,
- sends it as `PORT` and `LAUNCHER_PORT`,
- replaces `{port}` in setup/run commands,
- uses `http://localhost:{port}` as the browser URL when browser mode is on.

Change the range in config:

```json
"settings": {
  "port_range_start": 8100,
  "port_range_end": 8199
}
```

## Config Reference

Main config path:

```text
%APPDATA%\ProjectLauncher\projects.json
```

Example config is available at `launcher\projects.example.json`.

```json
{
  "name": "FastAPI App",
  "folder": "C:\\Users\\you\\Projects\\my-api",
  "setup": ["venv\\Scripts\\python.exe -m pip install -r requirements.txt"],
  "run": "venv\\Scripts\\python.exe -m uvicorn main:app --host 127.0.0.1 --port {port}",
  "wants_browser": true,
  "port": 8102,
  "url": "http://localhost:8102",
  "readiness": { "type": "port", "port": 8102, "timeout_seconds": 60 },
  "env": { "APP_ENV": "development" },
  "shell": "cmd",
  "accent": "#276a61"
}
```

Fields:

- `name`: project card title.
- `folder`: working directory for setup and run commands.
- `setup`: commands that finish before the server starts.
- `run`: long-running command; may include `{port}`.
- `wants_browser`: whether to show/open a browser URL.
- `port`: dedicated launcher port, or `"auto"` in import blocks.
- `url`: browser URL; normally `http://localhost:{port}`.
- `readiness`: `port`, `output`, or `none`; timeout defaults to 60 seconds.
- `env`: extra environment variables.
- `shell`: `cmd` or `powershell`.

## Import From An AI Assistant

Use **Import from AI** and paste:

```json
{
  "name": "My New App",
  "folder": "C:/path/to/app",
  "setup": ["npm install"],
  "run": "npm run dev",
  "wants_browser": true,
  "port": "auto"
}
```

`"port": "auto"` assigns the lowest available launcher port.

## Integration Clause

See `..\LAUNCHER_INTEGRATION.md`. Paste that clause into future app-building prompts so new apps read `PORT`, bind localhost, print a ready line, and return a registration block.

## Tests

```powershell
.\venv\Scripts\python.exe -m unittest tests.test_launcher_config tests.test_launcher_readiness tests.test_launcher_process
```

Full repo tests:

```powershell
.\venv\Scripts\python.exe -m unittest discover
```

## Manual QA Script

1. Temporarily rename `%APPDATA%\ProjectLauncher\projects.json` and run `python -m launcher`; confirm the welcome state appears.
2. Add a project:
   - Folder: `launcher\sample-project`
   - Run: `python server.py`
   - Browser: on
   - Port: auto-assigned, shown before saving
3. Start it and confirm the browser opens on the assigned `http://localhost:81xx`.
4. Add the sample again, confirm it receives a different port, and start both at once.
5. Force a port conflict by starting a server on one assigned port, then use **Use a free port instead**.
6. Break a folder path and use **Fix path...**.
7. Paste a registration block into **Import from AI** and confirm a project is created.
8. Confirm normal cards show no raw filesystem paths, no PIDs, and no red global config banner.

## Troubleshooting

- **Address already in use:** use **Use a free port instead** or **Stop the other program** on the card.
- **Folder missing:** use **Fix path...** on the card.
- **Command not found:** edit the project and check the run command and shell.
- **PowerShell execution policy:** choose `cmd`, or use PowerShell with `-ExecutionPolicy Bypass`.
- **Antivirus flags the EXE:** PyInstaller one-file apps can trigger cautious scanners. Build locally from source.
- **Tray support:** still skipped for stdlib Tkinter; reliable tray support needs a small third-party dependency.

## Later

Installer, real tray icon via `pystray`, project groups, run-command profiles, and auto-update.

