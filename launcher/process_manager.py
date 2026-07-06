import os
import queue
import subprocess
import threading
import time
import webbrowser
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from launcher.config_store import ProjectConfig, app_data_dir, readiness_for, validate_project
from launcher.readiness import is_port_open, port_freed, wait_for_port


LogCallback = Callable[[str, str], None]
StateCallback = Callable[[str, str, str], None]


@dataclass
class RunnerState:
    status: str = "Stopped"
    message: str = ""
    pid: int | None = None
    started_at: float = 0
    error_kind: str = ""
    details: str = ""
    conflict_port: int | None = None
    conflict_pid: str = ""


def shell_args(shell: str, command: str) -> list[str]:
    if shell == "powershell":
        return ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command]
    return ["cmd.exe", "/C", command]


def kill_process_tree(pid: int) -> bool:
    if os.name == "nt":
        completed = subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(pid)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return completed.returncode == 0
    try:
        os.kill(pid, 9)
        return True
    except OSError:
        return False


def pid_using_port(port: int) -> str:
    if os.name != "nt":
        return ""
    try:
        output = subprocess.check_output(["netstat", "-ano"], text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return ""
    needle = f":{int(port)}"
    for line in output.splitlines():
        if needle in line and "LISTENING" in line:
            return line.split()[-1]
    return ""


def process_name(pid: str | int) -> str:
    if os.name != "nt" or not pid:
        return ""
    try:
        output = subprocess.check_output(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return ""
    if not output or "No tasks are running" in output:
        return ""
    first = output.splitlines()[0].strip()
    if first.startswith('"'):
        return first.split('","', 1)[0].strip('"')
    return first.split(",", 1)[0].strip('"')


class ProjectRunner:
    def __init__(
        self,
        project: ProjectConfig,
        write_logs: bool = True,
        on_log: LogCallback | None = None,
        on_state: StateCallback | None = None,
    ) -> None:
        self.project = project
        self.write_logs = write_logs
        self.on_log = on_log
        self.on_state = on_state
        self.state = RunnerState()
        self.lines: deque[str] = deque(maxlen=2000)
        self.output_queue: queue.Queue[str] = queue.Queue()
        self.process: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._stop_requested = threading.Event()
        self._output_ready = threading.Event()
        self._lock = threading.Lock()
        self._log_file = None

    def update_project(self, project: ProjectConfig) -> None:
        if self.is_running():
            return
        self.project = project

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self) -> None:
        with self._lock:
            if self.state.status in {"Starting", "Running"}:
                return
            errors = validate_project(self.project)
            if errors:
                self._set_state("Error", errors[0])
                return
            readiness = readiness_for(self.project)
            if readiness.get("type") == "port":
                port = int(readiness.get("port"))
                if is_port_open(port):
                    holder = pid_using_port(port)
                    name = process_name(holder) if holder else ""
                    detail = f"Port {port} is already in use"
                    if holder:
                        detail += f" by PID {holder}"
                    if name:
                        detail += f" ({name})"
                    self._set_state(
                        "Error",
                        "Something else is already using this project's address.",
                        error_kind="port_conflict",
                        details=detail,
                        conflict_port=port,
                        conflict_pid=holder,
                    )
                    return
            self._stop_requested.clear()
            self._output_ready.clear()
            self._open_log_file()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def restart(self) -> None:
        self.stop()
        self.start()

    def stop(self, leave_running: bool = False) -> None:
        self._stop_requested.set()
        if leave_running:
            self._set_state("Stopped", "Left running outside the launcher.")
            self.process = None
            return
        process = self.process
        if process and process.poll() is None:
            self._append_log("Stopping process tree...")
            kill_process_tree(process.pid)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._append_log("Process did not exit after taskkill.")
        readiness = readiness_for(self.project)
        if readiness.get("type") == "port" and readiness.get("port"):
            freed = port_freed(int(readiness["port"]))
            if not freed:
                self._set_state("Error", f"Stopped, but port {readiness['port']} still appears busy.")
                return
        self.process = None
        self._set_state("Stopped", f"{self.project.name} stopped.")
        self._close_log_file()

    def clear_logs(self) -> None:
        self.lines.clear()

    def log_text(self) -> str:
        return "\n".join(self.lines)

    def _run(self) -> None:
        self._set_state("Starting", "Running setup commands.")
        env = os.environ.copy()
        env.update(self.project.env or {})
        if self.project.port:
            env["PORT"] = str(self.project.port)
            env["LAUNCHER_PORT"] = str(self.project.port)
        cwd = self.project.folder
        for command in self.project.setup:
            if self._stop_requested.is_set():
                self._set_state("Stopped", "Stopped before setup finished.")
                return
            if not self._run_setup(command, cwd, env):
                return

        self._set_state("Starting", "Starting server.")
        try:
            run_command = self.project.run.replace("{port}", str(self.project.port or ""))
            self.process = subprocess.Popen(
                shell_args(self.project.shell, run_command),
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            )
        except FileNotFoundError:
            self._set_state("Error", "Command shell was not found.")
            return
        except Exception as exc:
            self._set_state("Error", f"Could not start: {exc}")
            return

        self.state.pid = self.process.pid
        reader = threading.Thread(target=self._read_process_output, args=(self.process,), daemon=True)
        reader.start()
        time.sleep(2)
        if self.process.poll() is not None:
            self._set_state("Error", "The server exited right after starting. Check the logs.")
            return

        ready = self._wait_for_readiness()
        if self._stop_requested.is_set():
            return
        self._set_state("Running", "Server is running." if ready else "Readiness timed out; opened the URL anyway.")
        if self.project.url:
            webbrowser.open(self.project.url)
            self._append_log(f"Opened {self.project.url}")

        return_code = self.process.wait()
        if self._stop_requested.is_set():
            self._set_state("Stopped", f"{self.project.name} stopped.")
        elif return_code == 0:
            self._set_state("Stopped", f"{self.project.name} exited.")
        else:
            self._set_state("Error", f"Run command exited with code {return_code}.")
        self._close_log_file()

    def _run_setup(self, command: str, cwd: str, env: dict[str, str]) -> bool:
        command = command.replace("{port}", str(self.project.port or ""))
        self._append_log(f"> {command}")
        try:
            process = subprocess.Popen(
                shell_args(self.project.shell, command),
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except Exception as exc:
            self._set_state("Error", f"Could not run setup command: {exc}")
            return False
        self.process = process
        self._read_process_output(process)
        return_code = process.wait()
        self.process = None
        if return_code != 0:
            tail = "\n".join(list(self.lines)[-8:])
            self._set_state("Error", f"Setup failed: {command}\n{tail}")
            return False
        return True

    def _read_process_output(self, process: subprocess.Popen) -> None:
        if process.stdout is None:
            return
        for line in process.stdout:
            clean = line.rstrip("\r\n")
            self._append_log(clean)
            readiness = readiness_for(self.project)
            if readiness.get("type") == "output" and str(readiness.get("text", "")) in clean:
                self._output_ready.set()

    def _wait_for_readiness(self) -> bool:
        readiness = readiness_for(self.project)
        kind = readiness.get("type")
        timeout_seconds = int(readiness.get("timeout_seconds") or 60)
        if kind == "none":
            return True
        if kind == "port" and readiness.get("port"):
            self._append_log(f"Waiting for port {readiness['port']}...")
            return wait_for_port(int(readiness["port"]), timeout_seconds, self._stop_requested.is_set)
        if kind == "output":
            self._append_log(f"Waiting for output: {readiness.get('text')}")
            return self._output_ready.wait(timeout=timeout_seconds)
        return True

    def _set_state(
        self,
        status: str,
        message: str = "",
        error_kind: str = "",
        details: str = "",
        conflict_port: int | None = None,
        conflict_pid: str = "",
    ) -> None:
        self.state.status = status
        self.state.message = message
        self.state.error_kind = error_kind if status == "Error" else ""
        self.state.details = details
        self.state.conflict_port = conflict_port
        self.state.conflict_pid = conflict_pid
        if status == "Starting":
            self.state.started_at = time.time()
        if self.on_state:
            self.on_state(self.project.name, status, message)

    def _append_log(self, line: str) -> None:
        stamped = f"[{datetime.now().strftime('%H:%M:%S')}] {line}"
        self.lines.append(stamped)
        if self._log_file:
            try:
                self._log_file.write(stamped + "\n")
                self._log_file.flush()
            except Exception:
                pass
        if self.on_log:
            self.on_log(self.project.name, stamped)

    def _open_log_file(self) -> None:
        if not self.write_logs or self._log_file:
            return
        logs_dir = app_data_dir() / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(ch if ch.isalnum() else "-" for ch in self.project.name).strip("-") or "project"
        path = logs_dir / f"{safe_name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
        self._log_file = path.open("a", encoding="utf-8")

    def _close_log_file(self) -> None:
        if self._log_file:
            try:
                self._log_file.close()
            finally:
                self._log_file = None


class LauncherManager:
    def __init__(self, write_logs: bool = True, on_log: LogCallback | None = None, on_state: StateCallback | None = None) -> None:
        self.write_logs = write_logs
        self.on_log = on_log
        self.on_state = on_state
        self.runners: dict[str, ProjectRunner] = {}

    def sync_projects(self, projects: list[ProjectConfig]) -> None:
        names = {project.name for project in projects}
        for name in list(self.runners):
            if name not in names and not self.runners[name].is_running():
                del self.runners[name]
        for project in projects:
            runner = self.runners.get(project.name)
            if runner:
                runner.update_project(project)
            else:
                self.runners[project.name] = ProjectRunner(project, self.write_logs, self.on_log, self.on_state)

    def start(self, name: str) -> None:
        self.runners[name].start()

    def stop(self, name: str) -> None:
        self.runners[name].stop()

    def restart(self, name: str) -> None:
        self.runners[name].restart()

    def stop_all(self, leave_running: bool = False) -> None:
        for runner in self.runners.values():
            if runner.state.status in {"Starting", "Running"} or runner.is_running():
                runner.stop(leave_running=leave_running)

    def running_names(self) -> list[str]:
        return [
            name for name, runner in self.runners.items()
            if runner.state.status in {"Starting", "Running"} or runner.is_running()
        ]
