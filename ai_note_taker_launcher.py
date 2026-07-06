from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser


APP_NAME = "AI Note Taker"
HOST = "127.0.0.1"
PORT = 8000
BASE_URL = f"http://{HOST}:{PORT}"
HEALTH_URL = f"{BASE_URL}/healthz"


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent.parent
    return Path(__file__).resolve().parent


def log_dir() -> Path:
    root = os.environ.get("APPDATA")
    base = Path(root) if root else Path.home() / "AppData" / "Roaming"
    path = base / APP_NAME / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def show_error(message: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(APP_NAME, message)
        root.destroy()
    except Exception:
        print(message, file=sys.stderr)


def app_is_ready() -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=2) as response:
            if response.status != 200:
                return False
            payload = json.loads(response.read().decode("utf-8"))
            return bool(payload.get("ok"))
    except (OSError, ValueError, urllib.error.URLError):
        return False


def wait_until_ready(timeout_seconds: int = 35) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if app_is_ready():
            return True
        time.sleep(0.5)
    return False


def python_executable(root: Path) -> Path | str:
    bundled = root / "venv" / "Scripts" / "python.exe"
    if bundled.exists():
        return bundled
    if not getattr(sys, "frozen", False):
        return sys.executable
    return "python"


def start_server(root: Path) -> bool:
    main_file = root / "main.py"
    if not main_file.exists():
        show_error(f"Could not find main.py here:\n{root}")
        return False

    command = [
        str(python_executable(root)),
        "-m",
        "uvicorn",
        "main:app",
        "--host",
        HOST,
        "--port",
        str(PORT),
    ]
    env = os.environ.copy()
    env.setdefault("APP_ENV", "development")
    env.setdefault("PUBLIC_BASE_URL", BASE_URL)

    stdout_path = log_dir() / "ai-note-taker.out.log"
    stderr_path = log_dir() / "ai-note-taker.err.log"
    stdout = stdout_path.open("a", encoding="utf-8")
    stderr = stderr_path.open("a", encoding="utf-8")

    startupinfo = None
    creationflags = 0
    if os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    try:
        subprocess.Popen(
            command,
            cwd=str(root),
            env=env,
            stdout=stdout,
            stderr=stderr,
            stdin=subprocess.DEVNULL,
            startupinfo=startupinfo,
            creationflags=creationflags,
            close_fds=True,
        )
        return True
    except FileNotFoundError:
        show_error("Python was not found. Run setup.ps1 once, then try the icon again.")
        return False
    except Exception as exc:
        show_error(f"AI Note Taker could not start:\n{exc}")
        return False


def main() -> None:
    if app_is_ready():
        webbrowser.open(BASE_URL)
        return

    if not start_server(project_root()):
        return
    if wait_until_ready():
        webbrowser.open(BASE_URL)
        return

    webbrowser.open(BASE_URL)
    show_error(
        "AI Note Taker is still starting. If the page does not load in a moment, "
        f"check the logs in:\n{log_dir()}"
    )


if __name__ == "__main__":
    main()
