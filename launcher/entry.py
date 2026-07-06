import os
import sys
import traceback
from pathlib import Path


APP_DIR_NAME = "ProjectLauncher"


def app_data_dir() -> Path:
    root = os.environ.get("APPDATA")
    if root:
        return Path(root) / APP_DIR_NAME
    return Path.home() / ".projectlauncher"


def startup_marker_path() -> Path:
    return app_data_dir() / "startup-ok.txt"


def startup_error_path() -> Path:
    return app_data_dir() / "logs" / "startup-error.log"


def mark_startup_ok() -> None:
    path = startup_marker_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("Project Launcher initialized.\n", encoding="utf-8")


def install_exception_hook() -> None:
    def hook(exc_type, exc, tb):
        log_path = startup_error_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("".join(traceback.format_exception(exc_type, exc, tb)), encoding="utf-8")
        show_startup_error(log_path)

    sys.excepthook = hook


def show_startup_error(log_path: Path) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        root.title("Project Launcher")
        messagebox.showerror(
            "Project Launcher",
            f"Project Launcher couldn't start.\n\nA log with details was saved here:\n{log_path}",
        )
        root.destroy()
    except Exception:
        pass


def run() -> None:
    install_exception_hook()
    try:
        from launcher.app import main

        main()
    except Exception:
        log_path = startup_error_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(traceback.format_exc(), encoding="utf-8")
        show_startup_error(log_path)
