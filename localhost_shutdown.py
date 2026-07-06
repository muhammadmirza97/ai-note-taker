from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk


APP_NAME = "Localhost Shutdown"
CURRENT_PROJECT = Path(__file__).resolve().parent
LOCAL_ADDRESSES = {"127.0.0.1", "::1", "0.0.0.0"}
PROTECTED_NAMES = {
    "System",
    "Idle",
    "Registry",
    "smss",
    "csrss",
    "wininit",
    "services",
    "lsass",
    "svchost",
    "fontdrvhost",
    "dwm",
    "explorer",
    "RuntimeBroker",
    "SearchHost",
    "StartMenuExperienceHost",
    "ShellExperienceHost",
}
COMMON_DEV_PORTS = set(range(3000, 10000)) | {11434, 5000, 5173, 8000, 8001, 8080, 8501, 8888}


@dataclass(frozen=True)
class KnownProject:
    name: str
    folder: str

    @property
    def folded_folder(self) -> str:
        return _fold_path(self.folder)


@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    parent_pid: int
    name: str
    path: str
    command_line: str

    @property
    def haystack(self) -> str:
        return f"{self.name} {self.path} {self.command_line}".lower()

    @property
    def protected(self) -> bool:
        base_name = self.name.removesuffix(".exe")
        return self.pid in {0, 4, os.getpid()} or self.name in PROTECTED_NAMES or base_name in PROTECTED_NAMES


@dataclass(frozen=True)
class Listener:
    process: ProcessInfo
    ports: tuple[int, ...]
    addresses: tuple[str, ...]
    group_name: str
    group_folder: str

    @property
    def pid(self) -> int:
        return self.process.pid

    @property
    def name(self) -> str:
        return self.process.name

    @property
    def path(self) -> str:
        return self.process.path

    @property
    def command_line(self) -> str:
        return self.process.command_line

    @property
    def port_text(self) -> str:
        return ", ".join(str(port) for port in self.ports)

    @property
    def address_text(self) -> str:
        return ", ".join(self.addresses)

    @property
    def protected(self) -> bool:
        return self.process.protected

    @property
    def likely_dev(self) -> bool:
        if self.protected:
            return False
        if any(token in self.process.haystack for token in ("python", "node", "uvicorn", "streamlit", "vite", "ollama", "open-webui")):
            return True
        return any(port in COMMON_DEV_PORTS for port in self.ports)


def _fold_path(value: str) -> str:
    return str(value or "").replace("/", "\\").rstrip("\\").lower()


def _user_appdata() -> Path:
    root = os.environ.get("APPDATA")
    return Path(root) if root else Path.home() / "AppData" / "Roaming"


def _display_folder_name(folder: str) -> str:
    name = Path(folder).name
    return name.replace("-", " ").replace("_", " ").strip().title() or folder


def load_known_projects() -> list[KnownProject]:
    projects: list[KnownProject] = [KnownProject("AI Note Taker", str(CURRENT_PROJECT))]
    config_paths = [
        _user_appdata() / "ProjectLauncher" / "projects.json",
        _user_appdata() / "ProjectLauncher" / "launcher_projects.json",
    ]
    for path in config_paths:
        if not path.exists():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        items = raw.get("projects", raw if isinstance(raw, list) else [])
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            folder = str(item.get("folder") or item.get("path") or "").strip()
            if not folder:
                continue
            name = str(item.get("name") or _display_folder_name(folder)).strip()
            projects.append(KnownProject(name, folder))
    return _dedupe_projects(projects)


def _dedupe_projects(projects: list[KnownProject]) -> list[KnownProject]:
    seen: set[str] = set()
    unique: list[KnownProject] = []
    for project in projects:
        key = project.folded_folder
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(project)
    return unique


def run_powershell(script: str) -> str:
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=25,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "PowerShell command failed.")
    return completed.stdout


def discover_processes() -> dict[int, ProcessInfo]:
    script = r"""
Get-CimInstance Win32_Process |
  Select-Object ProcessId,ParentProcessId,Name,ExecutablePath,CommandLine |
  ConvertTo-Csv -NoTypeInformation
"""
    rows = csv.DictReader(io.StringIO(run_powershell(script)))
    processes: dict[int, ProcessInfo] = {}
    for row in rows:
        try:
            pid = int(row.get("ProcessId") or 0)
        except ValueError:
            continue
        try:
            parent_pid = int(row.get("ParentProcessId") or 0)
        except ValueError:
            parent_pid = 0
        processes[pid] = ProcessInfo(
            pid=pid,
            parent_pid=parent_pid,
            name=row.get("Name", "") or "unknown",
            path=row.get("ExecutablePath", "") or "",
            command_line=row.get("CommandLine", "") or "",
        )
    return processes


def discover_listener_rows() -> list[dict[str, str]]:
    script = r"""
$connections = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
  Where-Object { @('127.0.0.1','::1','0.0.0.0') -contains $_.LocalAddress } |
  Select-Object LocalAddress,LocalPort,OwningProcess
$rows = foreach ($group in ($connections | Group-Object OwningProcess)) {
  [PSCustomObject]@{
    Pid = [int]$group.Name
    Ports = (($group.Group | Sort-Object LocalPort | Select-Object -ExpandProperty LocalPort -Unique) -join ';')
    Addresses = (($group.Group | Sort-Object LocalAddress | Select-Object -ExpandProperty LocalAddress -Unique) -join ';')
  }
}
$rows | Sort-Object Pid | ConvertTo-Csv -NoTypeInformation
"""
    return list(csv.DictReader(io.StringIO(run_powershell(script))))


def ancestry(pid: int, processes: dict[int, ProcessInfo], limit: int = 8) -> list[ProcessInfo]:
    chain: list[ProcessInfo] = []
    seen: set[int] = set()
    current = processes.get(pid)
    while current and current.pid not in seen and len(chain) < limit:
        chain.append(current)
        seen.add(current.pid)
        current = processes.get(current.parent_pid)
    return chain


def project_for_process(chain: list[ProcessInfo], projects: list[KnownProject]) -> tuple[str, str]:
    chain_text = "\n".join(item.haystack for item in chain)
    for project in projects:
        folder = project.folded_folder
        if folder and folder in chain_text:
            return project.name, project.folder

    if "open-webui" in chain_text:
        return "Open WebUI / Ollama", "OpenWebUI local runtime"
    if "ollama" in chain_text or "llama-server" in chain_text:
        return "Ollama", "Local AI model runtime"
    if "ai-learning-helper" in chain_text:
        return "AI Learning Helper", "AI Project\\ai-learning-helper"
    if "\\ai note taker\\" in chain_text:
        return "AI Note Taker", str(CURRENT_PROJECT)
    if "code.exe" in chain_text or "node-pty" in chain_text:
        return "VS Code", "VS Code background/local services"

    first = chain[0] if chain else None
    if first and first.path:
        return f"{first.name}", str(Path(first.path).parent)
    return "Unknown local program", ""


def discover_listeners() -> list[Listener]:
    projects = load_known_projects()
    processes = discover_processes()
    listeners: list[Listener] = []
    for row in discover_listener_rows():
        try:
            pid = int(row["Pid"])
        except (KeyError, ValueError):
            continue
        ports = tuple(int(item) for item in row.get("Ports", "").split(";") if item.strip().isdigit())
        addresses = tuple(item for item in row.get("Addresses", "").split(";") if item.strip())
        if not ports:
            continue
        process = processes.get(pid) or ProcessInfo(pid, 0, "unknown", "", "")
        group_name, group_folder = project_for_process(ancestry(pid, processes), projects)
        listeners.append(Listener(process, ports, addresses, group_name, group_folder))
    return listeners


def kill_tree(pid: int) -> tuple[bool, str]:
    completed = subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
    )
    return completed.returncode == 0, (completed.stdout + completed.stderr).strip()


class LocalhostShutdownApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1180x700")
        self.minsize(940, 540)
        self.configure(bg="#0b0d10")
        self.listeners: dict[str, Listener] = {}
        self.groups: dict[str, list[Listener]] = {}
        self.status = tk.StringVar(value="Ready.")
        self.include_protected = tk.BooleanVar(value=False)
        self._build()
        self.refresh()

    def _build(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background="#10141a", fieldbackground="#10141a", foreground="#d1d7e0", rowheight=30)
        style.configure("Treeview.Heading", background="#151a22", foreground="#d1d7e0")
        style.map("Treeview", background=[("selected", "#24423d")])

        header = tk.Frame(self, bg="#0b0d10", padx=18, pady=14)
        header.pack(fill="x")
        tk.Label(header, text=APP_NAME, bg="#0b0d10", fg="#d1d7e0", font=("Segoe UI", 18, "bold")).pack(side="left")
        tk.Button(header, text="Refresh", command=self.refresh, bg="#151a22", fg="#d1d7e0", relief="flat", padx=12, pady=7).pack(side="right")

        note = (
            "Grouped by app/project. Expand a group to see which program is running it, "
            "which localhost ports it owns, and the command/path behind it."
        )
        tk.Label(self, text=note, bg="#0b0d10", fg="#788394", wraplength=1080, justify="left").pack(fill="x", padx=18)

        columns = ("pid", "program", "ports", "addresses", "type", "running_by")
        self.tree = ttk.Treeview(self, columns=columns, show="tree headings", selectmode="extended")
        self.tree.heading("#0", text="App / Project")
        self.tree.column("#0", width=230, anchor="w")
        headings = {
            "pid": "PID",
            "program": "Program",
            "ports": "Ports",
            "addresses": "Addresses",
            "type": "Type",
            "running_by": "Running by / command",
        }
        widths = {"pid": 70, "program": 135, "ports": 135, "addresses": 110, "type": 105, "running_by": 455}
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(column, width=widths[column], anchor="w")
        self.tree.pack(fill="both", expand=True, padx=18, pady=12)

        options = tk.Frame(self, bg="#0b0d10", padx=18)
        options.pack(fill="x")
        tk.Checkbutton(
            options,
            text="Show protected Windows processes",
            variable=self.include_protected,
            command=self.refresh,
            bg="#0b0d10",
            fg="#9aa4b2",
            selectcolor="#10141a",
            activebackground="#0b0d10",
            activeforeground="#d1d7e0",
        ).pack(side="left")

        actions = tk.Frame(self, bg="#0b0d10", padx=18, pady=14)
        actions.pack(fill="x")
        tk.Button(actions, text="Stop selected app/process", command=self.stop_selected, bg="#1f3430", fg="#d1fff4", relief="flat", padx=14, pady=9).pack(side="left")
        tk.Button(actions, text="Stop common dev apps", command=self.stop_dev_ports, bg="#172530", fg="#dbeafe", relief="flat", padx=14, pady=9).pack(side="left", padx=10)
        tk.Button(actions, text="Stop all listed", command=self.stop_all_listed, bg="#341d1d", fg="#ffd7d7", relief="flat", padx=14, pady=9).pack(side="left")
        tk.Button(actions, text="Close", command=self.destroy, bg="#151a22", fg="#d1d7e0", relief="flat", padx=14, pady=9).pack(side="right")

        tk.Label(self, textvariable=self.status, bg="#050608", fg="#9aa4b2", anchor="w", padx=14, pady=8).pack(fill="x", side="bottom")

    def refresh(self) -> None:
        try:
            discovered = discover_listeners()
            self.listeners.clear()
            self.groups.clear()
            self.tree.delete(*self.tree.get_children())
            for listener in discovered:
                if listener.protected and not self.include_protected.get():
                    continue
                self.listeners[str(listener.pid)] = listener
                self.groups.setdefault(listener.group_name, []).append(listener)

            for group_name, listeners in sorted(self.groups.items(), key=lambda item: item[0].lower()):
                group_id = f"group::{group_name}"
                all_ports = sorted({port for item in listeners for port in item.ports})
                app_type = "protected" if all(item.protected for item in listeners) else "dev app" if any(item.likely_dev for item in listeners) else "local app"
                group_folder = next((item.group_folder for item in listeners if item.group_folder), "")
                self.tree.insert(
                    "",
                    "end",
                    iid=group_id,
                    text=group_name,
                    values=("", f"{len(listeners)} process(es)", ", ".join(map(str, all_ports)), "", app_type, group_folder),
                    open=True,
                )
                for listener in sorted(listeners, key=lambda item: (min(item.ports), item.pid)):
                    kind = "protected" if listener.protected else "dev likely" if listener.likely_dev else "local"
                    command = listener.command_line or listener.path
                    self.tree.insert(
                        group_id,
                        "end",
                        iid=f"pid::{listener.pid}",
                        text="",
                        values=(listener.pid, listener.name, listener.port_text, listener.address_text, kind, command),
                    )
            self.status.set(f"Found {len(self.groups)} app group(s), {len(self.listeners)} local listener process(es).")
        except Exception as exc:
            self.status.set(str(exc))
            messagebox.showerror(APP_NAME, str(exc))

    def selected_listeners(self) -> list[Listener]:
        selected: dict[int, Listener] = {}
        for item_id in self.tree.selection():
            if item_id.startswith("pid::"):
                listener = self.listeners.get(item_id.removeprefix("pid::"))
                if listener:
                    selected[listener.pid] = listener
            elif item_id.startswith("group::"):
                for listener in self.groups.get(item_id.removeprefix("group::"), []):
                    selected[listener.pid] = listener
        return list(selected.values())

    def _confirm_and_stop(self, listeners: list[Listener], label: str) -> None:
        targets = [listener for listener in listeners if not listener.protected]
        protected_count = len(listeners) - len(targets)
        if not targets:
            messagebox.showinfo(APP_NAME, "No stoppable local listener was selected.")
            return
        by_group: dict[str, list[Listener]] = {}
        for listener in targets:
            by_group.setdefault(listener.group_name, []).append(listener)
        lines: list[str] = []
        for group, items in sorted(by_group.items()):
            ports = sorted({port for item in items for port in item.ports})
            names = ", ".join(sorted({item.name for item in items}))
            lines.append(f"- {group}: {names} on {', '.join(map(str, ports))}")
        summary = "\n".join(lines[:12])
        if len(lines) > 12:
            summary += f"\n- ...and {len(lines) - 12} more app group(s)"
        if protected_count:
            summary += f"\n\nSkipped {protected_count} protected Windows process(es)."
        if not messagebox.askyesno(APP_NAME, f"{label}?\n\n{summary}"):
            return
        stopped = []
        failed = []
        for listener in targets:
            ok, details = kill_tree(listener.pid)
            if ok:
                stopped.append(f"{listener.group_name}: {listener.name} ({listener.pid})")
            else:
                failed.append(f"{listener.group_name}: {listener.name} ({listener.pid}): {details or 'failed'}")
        self.refresh()
        message = f"Stopped {len(stopped)} process(es)."
        if failed:
            message += f" Failed: {len(failed)}."
        self.status.set(message)
        if failed:
            messagebox.showwarning(APP_NAME, message + "\n\n" + "\n".join(failed[:8]))

    def stop_selected(self) -> None:
        self._confirm_and_stop(self.selected_listeners(), "Stop selected localhost app/process")

    def stop_dev_ports(self) -> None:
        selected = [listener for listener in self.listeners.values() if listener.likely_dev]
        self._confirm_and_stop(selected, "Stop common local development apps")

    def stop_all_listed(self) -> None:
        self._confirm_and_stop(list(self.listeners.values()), "Stop every non-protected listed localhost program")


def main() -> None:
    if os.name != "nt":
        print("This utility is intended for Windows.")
        sys.exit(1)
    LocalhostShutdownApp().mainloop()


if __name__ == "__main__":
    main()
