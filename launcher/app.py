import json
import logging
import os
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from launcher.config_store import (
    LauncherConfig,
    ProjectConfig,
    app_data_dir,
    apply_project_port,
    assign_missing_ports,
    assign_new_port,
    default_config_path,
    drop_broken_sample_projects,
    duplicate_ports,
    find_free_port,
    load_config,
    project_from_registration,
    save_config,
    validate_config,
    validate_project,
)
from launcher.entry import mark_startup_ok
from launcher.process_manager import LauncherManager, kill_process_tree, process_name


APP_NAME = "Project Launcher"
BG = "#f4f7f5"
SURFACE = "#ffffff"
TEXT = "#1f2937"
MUTED = "#667085"
GREEN = "#24745d"
RED = "#b42318"
YELLOW = "#a15c07"
SOFT_RED = "#fff1f0"
SOFT_YELLOW = "#fff7e6"
SOFT_GREEN = "#e8f5ef"


def setup_logging() -> None:
    log_dir = app_data_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_dir / "launcher.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def set_startup_enabled(enabled: bool) -> None:
    if os.name != "nt":
        return
    import winreg

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            exe = Path(os.sys.executable).resolve()
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{exe}"')
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


class ToolTip:
    def __init__(self, widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tip = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _event=None) -> None:
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self.tip, text=self.text, bg="#111827", fg="#ffffff", padx=8, pady=4).pack()

    def hide(self, _event=None) -> None:
        if self.tip:
            self.tip.destroy()
            self.tip = None


def make_button(parent, text, command, bg="#ffffff", fg=TEXT, padx=14, pady=9):
    button = tk.Button(
        parent,
        text=text,
        command=command,
        bg=bg,
        fg=fg,
        activebackground=bg,
        activeforeground=fg,
        relief="flat",
        bd=0,
        padx=padx,
        pady=pady,
        cursor="hand2",
        font=("Segoe UI", 10, "bold"),
    )
    return button


class ProjectDialog(tk.Toplevel):
    def __init__(self, parent, config: LauncherConfig, project: ProjectConfig | None = None) -> None:
        super().__init__(parent)
        self.title("Edit project" if project else "Add project")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self.config_data = config
        self.project = project
        initial_port = project.port if project and project.port else find_free_port(config, exclude_name=project.name if project else "")
        self.result: ProjectConfig | None = None
        self.vars = {
            "name": tk.StringVar(value=project.name if project else ""),
            "folder": tk.StringVar(value=project.folder if project else ""),
            "run": tk.StringVar(value=project.run if project else ""),
            "wants_browser": tk.BooleanVar(value=project.wants_browser if project else True),
            "port": tk.StringVar(value=str(initial_port)),
            "setup": tk.StringVar(value="\n".join(project.setup) if project else ""),
            "env": tk.StringVar(value=self._env_text(project.env if project else {})),
            "shell": tk.StringVar(value=project.shell if project else "cmd"),
            "accent": tk.StringVar(value=project.accent if project else GREEN),
        }
        self.message = tk.StringVar(value=f"This project will run at http://localhost:{initial_port}")
        self.advanced_open = tk.BooleanVar(value=False)
        self._build()
        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Return>", lambda _event: self._save())
        self.wait_visibility()
        self.focus_force()

    def _build(self) -> None:
        frame = tk.Frame(self, bg=BG, padx=22, pady=22)
        frame.grid(row=0, column=0, sticky="nsew")
        tk.Label(frame, text="Add your local project", bg=BG, fg=TEXT, font=("Segoe UI", 18, "bold")).grid(row=0, column=0, columnspan=3, sticky="w")
        tk.Label(frame, text="Tell the launcher where it lives and how to start it.", bg=BG, fg=MUTED, font=("Segoe UI", 10)).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 14))

        self._entry(frame, 2, "What should we call it?", "name", "Observation Generator")
        self._entry(frame, 3, "Where is your project folder?", "folder", "C:\\Users\\you\\Projects\\my-app", browse=True)
        self._entry(frame, 4, "How do you start it?", "run", "npm run dev  or  python app.py")

        browser = tk.Checkbutton(frame, text="Open this app in the browser", variable=self.vars["wants_browser"], bg=BG, fg=TEXT, command=self._update_port_message)
        browser.grid(row=5, column=1, sticky="w", pady=7)

        tk.Label(frame, text="Which local address should it use?", bg=BG, fg=TEXT).grid(row=6, column=0, sticky="w", pady=7)
        port_row = tk.Frame(frame, bg=BG)
        port_row.grid(row=6, column=1, sticky="w", pady=7)
        tk.Label(port_row, text="localhost:", bg=BG, fg=MUTED).pack(side="left")
        port_entry = ttk.Entry(port_row, textvariable=self.vars["port"], width=8)
        port_entry.pack(side="left")
        ToolTip(port_entry, "The launcher also sends this as PORT and LAUNCHER_PORT.")
        self.vars["port"].trace_add("write", lambda *_: self._update_port_message())

        tk.Label(frame, textvariable=self.message, bg=BG, fg=GREEN).grid(row=7, column=1, sticky="w", pady=(0, 8))

        advanced_button = make_button(frame, "Advanced", self._toggle_advanced, bg="#e8ece8", fg=TEXT, padx=10, pady=6)
        advanced_button.grid(row=8, column=1, sticky="w", pady=6)
        self.advanced = tk.Frame(frame, bg=BG)

        tk.Label(self.advanced, text="Setup commands, one per line", bg=BG, fg=TEXT).grid(row=0, column=0, sticky="nw", pady=4)
        self.setup_text = tk.Text(self.advanced, width=58, height=4)
        self.setup_text.insert("1.0", self.vars["setup"].get())
        self.setup_text.grid(row=0, column=1, sticky="ew", pady=4)

        tk.Label(self.advanced, text="Environment variables", bg=BG, fg=TEXT).grid(row=1, column=0, sticky="nw", pady=4)
        self.env_text = tk.Text(self.advanced, width=58, height=4)
        self.env_text.insert("1.0", self.vars["env"].get())
        self.env_text.grid(row=1, column=1, sticky="ew", pady=4)

        tk.Label(self.advanced, text="Shell", bg=BG, fg=TEXT).grid(row=2, column=0, sticky="w", pady=4)
        ttk.Combobox(self.advanced, textvariable=self.vars["shell"], values=["cmd", "powershell"], state="readonly").grid(row=2, column=1, sticky="w", pady=4)
        tk.Label(self.advanced, text="Use {port} in your command, or read PORT in your app.", bg=BG, fg=MUTED).grid(row=3, column=1, sticky="w", pady=(0, 6))

        actions = tk.Frame(frame, bg=BG)
        actions.grid(row=10, column=1, sticky="e", pady=(16, 0))
        make_button(actions, "Cancel", self.destroy, bg="#e8ece8").pack(side="right", padx=(8, 0))
        make_button(actions, "Save project", self._save, bg=GREEN, fg="#ffffff").pack(side="right")

    def _entry(self, frame, row: int, label: str, key: str, placeholder: str, browse: bool = False) -> None:
        tk.Label(frame, text=label, bg=BG, fg=TEXT).grid(row=row, column=0, sticky="w", pady=7)
        entry = ttk.Entry(frame, textvariable=self.vars[key], width=60)
        entry.grid(row=row, column=1, sticky="ew", pady=7)
        ToolTip(entry, placeholder)
        if browse:
            make_button(frame, "Browse", self._browse_folder, bg="#e8ece8", padx=10, pady=6).grid(row=row, column=2, padx=(8, 0))

    def _toggle_advanced(self) -> None:
        if self.advanced.winfo_ismapped():
            self.advanced.grid_remove()
        else:
            self.advanced.grid(row=9, column=0, columnspan=3, sticky="ew", pady=(4, 0))

    def _browse_folder(self) -> None:
        folder = filedialog.askdirectory(parent=self, title="Choose project folder")
        if folder:
            self.vars["folder"].set(folder)

    def _update_port_message(self) -> None:
        port = self.vars["port"].get().strip()
        if not port.isdigit():
            self.message.set("Use a number like 8101.")
            return
        self.message.set(f"This project will run at http://localhost:{port}" if self.vars["wants_browser"].get() else f"This project will use port {port}.")

    def _save(self) -> None:
        try:
            port = int(self.vars["port"].get())
        except ValueError:
            self.message.set("Use a number like 8101.")
            return
        project = ProjectConfig(
            name=self.vars["name"].get().strip(),
            folder=self.vars["folder"].get().strip(),
            setup=[line.strip() for line in self.setup_text.get("1.0", "end").splitlines() if line.strip()],
            run=self.vars["run"].get().strip(),
            port=port,
            wants_browser=bool(self.vars["wants_browser"].get()),
            env=self._parse_env(self.env_text.get("1.0", "end")),
            shell=self.vars["shell"].get(),
            accent=self.vars["accent"].get().strip() or GREEN,
        )
        apply_project_port(project, port)
        errors = validate_project(project)
        used_elsewhere = {item.port for item in self.config_data.projects if item.name != (self.project.name if self.project else "")}
        if project.port in used_elsewhere:
            errors.append("Another project already uses this port.")
        if errors:
            self.message.set(errors[0])
            return
        self.result = project
        self.destroy()

    @staticmethod
    def _env_text(env: dict[str, str]) -> str:
        return "\n".join(f"{key}={value}" for key, value in env.items())

    @staticmethod
    def _parse_env(text: str) -> dict[str, str]:
        env: dict[str, str] = {}
        for line in text.splitlines():
            if not line.strip() or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
        return env


class ImportDialog(tk.Toplevel):
    def __init__(self, parent, config: LauncherConfig) -> None:
        super().__init__(parent)
        self.title("Import from AI assistant")
        self.transient(parent)
        self.grab_set()
        self.config_data = config
        self.result: ProjectConfig | None = None
        self.message = tk.StringVar(value="Paste the registration block from your app builder.")
        frame = tk.Frame(self, bg=BG, padx=22, pady=22)
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text="Import a project", bg=BG, fg=TEXT, font=("Segoe UI", 18, "bold")).pack(anchor="w")
        self.text = tk.Text(frame, width=76, height=14)
        self.text.pack(fill="both", expand=True, pady=12)
        self.text.insert("1.0", '{\n  "name": "My New App",\n  "folder": "C:/path/to/app",\n  "setup": ["npm install"],\n  "run": "npm run dev",\n  "wants_browser": true,\n  "port": "auto"\n}')
        tk.Label(frame, textvariable=self.message, bg=BG, fg=MUTED).pack(anchor="w")
        actions = tk.Frame(frame, bg=BG)
        actions.pack(anchor="e", pady=(14, 0))
        make_button(actions, "Cancel", self.destroy, bg="#e8ece8").pack(side="right", padx=(8, 0))
        make_button(actions, "Import project", self._import, bg=GREEN, fg="#ffffff").pack(side="right")

    def _import(self) -> None:
        try:
            raw = json.loads(self.text.get("1.0", "end"))
            project = project_from_registration(raw, self.config_data)
            errors = validate_project(project)
            if errors:
                self.message.set(errors[0])
                return
            self.result = project
            self.destroy()
        except Exception as exc:
            self.message.set(f"That registration block is not valid JSON: {exc}")


class LogWindow(tk.Toplevel):
    def __init__(self, parent, runner) -> None:
        super().__init__(parent)
        self.runner = runner
        self.title(f"Logs - {runner.project.name}")
        self.geometry("820x460")
        self.autoscroll = tk.BooleanVar(value=True)
        toolbar = ttk.Frame(self, padding=(8, 8, 8, 0))
        toolbar.pack(fill="x")
        ttk.Checkbutton(toolbar, text="Auto-scroll", variable=self.autoscroll).pack(side="left")
        ttk.Button(toolbar, text="Copy all", command=self.copy_all).pack(side="right")
        ttk.Button(toolbar, text="Clear", command=self.clear).pack(side="right", padx=8)
        self.text = tk.Text(self, wrap="word", bg="#111827", fg="#e5e7eb", insertbackground="#e5e7eb")
        self.text.pack(fill="both", expand=True, padx=8, pady=8)
        self.refresh()

    def refresh(self) -> None:
        if not self.winfo_exists():
            return
        self.text.delete("1.0", "end")
        self.text.insert("1.0", self.runner.log_text())
        if self.autoscroll.get():
            self.text.see("end")
        self.after(750, self.refresh)

    def copy_all(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(self.runner.log_text())

    def clear(self) -> None:
        self.runner.clear_logs()


class LauncherApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        setup_logging()
        self.title(APP_NAME)
        self._set_window_icon()
        self.geometry("1100x740")
        self.minsize(900, 600)
        self.configure(bg=BG)
        self.config_path = default_config_path()
        self.config_data = LauncherConfig()
        self.cards: dict[str, dict[str, tk.Widget]] = {}
        self.status_message = tk.StringVar(value="Ready")
        self.startup_enabled = tk.BooleanVar(value=False)
        self.manager = LauncherManager(on_log=self._on_log, on_state=self._on_state)
        self._build_ui()
        self.load_config()
        mark_startup_ok()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))

        header = tk.Frame(self, bg=BG, padx=24, pady=20)
        header.pack(fill="x")
        tk.Label(header, text="Your local apps", bg=BG, fg=TEXT, font=("Segoe UI", 24, "bold")).pack(side="left")
        make_button(header, "+ Add project", self.add_project, bg=GREEN, fg="#ffffff").pack(side="right")
        make_button(header, "Import from AI", self.import_project, bg="#e8ece8").pack(side="right", padx=8)
        make_button(header, "Stop all", self.stop_all, bg="#ffe4e1", fg=RED).pack(side="right")
        make_button(header, "Refresh", self.load_config, bg="#e8ece8").pack(side="right", padx=8)

        sub = tk.Frame(self, bg=BG, padx=24)
        sub.pack(fill="x")
        tk.Label(sub, text="Add your local projects once, then start them with one click.", bg=BG, fg=MUTED, font=("Segoe UI", 11)).pack(side="left")
        ttk.Checkbutton(sub, text="Start on Windows login", variable=self.startup_enabled, command=self.toggle_startup).pack(side="right")

        self.global_problem = tk.Frame(self, bg=SOFT_RED, padx=14, pady=10)
        self.global_problem_label = tk.Label(self.global_problem, text="", bg=SOFT_RED, fg=RED)
        self.global_problem_label.pack(side="left")
        make_button(self.global_problem, "Fix it", self.open_config_file, bg="#ffffff", fg=RED, padx=10, pady=5).pack(side="right")

        canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.card_frame = tk.Frame(canvas, bg=BG)
        self.card_frame.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.card_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(24, 0), pady=18)
        scrollbar.pack(side="right", fill="y", pady=18)

        footer = tk.Frame(self, bg=SURFACE, padx=14, pady=10)
        footer.pack(fill="x", side="bottom")
        tk.Label(footer, textvariable=self.status_message, bg=SURFACE, fg=MUTED).pack(side="left")

    def _set_window_icon(self) -> None:
        image = tk.PhotoImage(width=32, height=32)
        image.put(GREEN, to=(0, 0, 32, 32))
        image.put("#ffffff", to=(7, 8, 12, 24))
        image.put("#ffffff", to=(12, 8, 22, 13))
        image.put("#ffffff", to=(12, 19, 24, 24))
        image.put("#d7eee5", to=(22, 10, 26, 14))
        self.iconphoto(True, image)
        self._icon_image = image

    def load_config(self) -> None:
        try:
            self.global_problem.pack_forget()
            self.config_data = load_config(self.config_path)
            changed = drop_broken_sample_projects(self.config_data)
            changed = assign_missing_ports(self.config_data) or changed
            if changed:
                save_config(self.config_data, self.config_path)
            self.startup_enabled.set(bool(self.config_data.settings.get("start_on_windows_login")))
            self.manager.write_logs = bool(self.config_data.settings.get("write_logs", True))
            self.manager.sync_projects(self.config_data.projects)
            self.render_cards()
            self.status_message.set("Ready when you are.")
        except Exception as exc:
            logging.exception("Failed to load config")
            self.global_problem_label.configure(text="The project list could not be read.")
            self.global_problem.pack(fill="x", padx=24, pady=(10, 0))
            self.status_message.set("Open the config file and fix the JSON, then press Refresh.")

    def save_and_reload(self) -> None:
        save_config(self.config_data, self.config_path)
        self.load_config()

    def render_cards(self) -> None:
        for child in self.card_frame.winfo_children():
            child.destroy()
        self.cards.clear()
        active_projects = self.config_data.projects
        if not active_projects:
            self._render_welcome()
            return
        duplicates = duplicate_ports(active_projects)
        for index, project in enumerate(active_projects):
            self._render_card(index, project, project.port in duplicates)

    def _render_welcome(self) -> None:
        empty = tk.Frame(self.card_frame, bg=SURFACE, padx=32, pady=32, highlightbackground="#d8ded8", highlightthickness=1)
        empty.grid(row=0, column=0, sticky="ew", padx=4, pady=4)
        tk.Label(empty, text="Add your local projects once, then start them with one click.", bg=SURFACE, fg=TEXT, font=("Segoe UI", 17, "bold")).pack(anchor="w")
        tk.Label(empty, text="The launcher will give each app its own localhost address automatically.", bg=SURFACE, fg=MUTED).pack(anchor="w", pady=(8, 16))
        make_button(empty, "Add your first project", self.add_project, bg=GREEN, fg="#ffffff", padx=20, pady=12).pack(anchor="w")

    def _render_card(self, index: int, project: ProjectConfig, duplicate_port: bool = False) -> None:
        card = tk.Frame(self.card_frame, bg=SURFACE, padx=18, pady=18, highlightbackground="#d8ded8", highlightthickness=1)
        card.grid(row=index // 2, column=index % 2, sticky="nsew", padx=10, pady=10)
        self.card_frame.columnconfigure(index % 2, weight=1)
        tk.Label(card, text=project.name, bg=SURFACE, fg=TEXT, font=("Segoe UI", 17, "bold")).grid(row=0, column=0, sticky="w")
        menu_button = make_button(card, "...", lambda p=project: self.show_project_menu(p), bg="#edf1ed", padx=10, pady=5)
        menu_button.grid(row=0, column=1, sticky="e")
        ToolTip(menu_button, "More actions")

        status = tk.Label(card, text="", bg="#eceff1", fg=TEXT, padx=10, pady=5, font=("Segoe UI", 9, "bold"))
        status.grid(row=1, column=0, sticky="w", pady=(12, 4))
        url = tk.Label(card, text="", bg=SURFACE, fg=GREEN, cursor="hand2", font=("Segoe UI", 10, "underline"))
        url.grid(row=2, column=0, sticky="w")
        url.bind("<Button-1>", lambda _event, p=project: self.open_browser(p))

        issue = tk.Frame(card, bg=SURFACE)
        issue.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        actions = tk.Frame(card, bg=SURFACE)
        actions.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(16, 0))
        primary = make_button(actions, "Start", lambda name=project.name: self.toggle_project(name), bg=GREEN, fg="#ffffff", padx=28, pady=12)
        primary.pack(side="left")
        browser = make_button(actions, "Open in browser", lambda p=project: self.open_browser(p), bg="#e8ece8", fg=GREEN, padx=14, pady=12)
        browser.pack(side="left", padx=10)

        self.cards[project.name] = {"status": status, "primary": primary, "browser": browser, "url": url, "issue": issue}
        self._apply_state(project.name, self.manager.runners.get(project.name).state.status if project.name in self.manager.runners else "Stopped", "")
        self._render_card_issues(project, duplicate_port)

    def _render_card_issues(self, project: ProjectConfig, duplicate_port: bool = False) -> None:
        card = self.cards.get(project.name)
        if not card:
            return
        issue = card["issue"]
        for child in issue.winfo_children():
            child.destroy()
        if not Path(project.folder).exists():
            self._issue_row(issue, "This project's folder can't be found.", "Fix path...", lambda p=project: self.edit_project(p))
        elif duplicate_port:
            self._issue_row(issue, "Another project is using this same address.", "Assign new port", lambda p=project: self.assign_new_port_and_save(p.name))

    def _issue_row(self, parent, text: str, action: str, command) -> None:
        box = tk.Frame(parent, bg=SOFT_YELLOW, padx=10, pady=8)
        box.pack(fill="x")
        tk.Label(box, text=text, bg=SOFT_YELLOW, fg=YELLOW).pack(side="left")
        make_button(box, action, command, bg="#ffffff", fg=YELLOW, padx=10, pady=5).pack(side="right")

    def show_project_menu(self, project: ProjectConfig) -> None:
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Restart", command=lambda: self.restart_project(project.name))
        menu.add_command(label="Open folder", command=lambda: self.open_folder(project))
        menu.add_command(label="Edit", command=lambda: self.edit_project(project))
        menu.add_command(label="View logs", command=lambda: self.show_logs(project.name))
        menu.add_separator()
        menu.add_command(label="Remove", command=lambda: self.remove_project(project))
        menu.tk_popup(self.winfo_pointerx(), self.winfo_pointery())

    def toggle_project(self, name: str) -> None:
        runner = self.manager.runners[name]
        if runner.state.status in {"Starting", "Running"} or runner.is_running():
            self.manager.stop(name)
        else:
            self.status_message.set(f"Starting {name}... usually takes a few seconds.")
            self.manager.start(name)

    def restart_project(self, name: str) -> None:
        self.manager.restart(name)

    def stop_all(self) -> None:
        self.manager.stop_all()

    def add_project(self) -> None:
        dialog = ProjectDialog(self, self.config_data)
        self.wait_window(dialog)
        if dialog.result:
            self.config_data.projects.append(dialog.result)
            self.save_and_reload()

    def import_project(self) -> None:
        dialog = ImportDialog(self, self.config_data)
        self.wait_window(dialog)
        if dialog.result:
            self.config_data.projects.append(dialog.result)
            self.save_and_reload()

    def edit_project(self, project: ProjectConfig) -> None:
        dialog = ProjectDialog(self, self.config_data, project)
        self.wait_window(dialog)
        if dialog.result:
            self.config_data.projects = [dialog.result if item.name == project.name else item for item in self.config_data.projects]
            self.save_and_reload()

    def remove_project(self, project: ProjectConfig) -> None:
        runner = self.manager.runners.get(project.name)
        if runner and runner.is_running():
            messagebox.showerror(APP_NAME, "Stop this project before removing it.")
            return
        if messagebox.askyesno(APP_NAME, f"Remove {project.name}?"):
            self.config_data.projects = [item for item in self.config_data.projects if item.name != project.name]
            self.save_and_reload()

    def assign_new_port_and_save(self, name: str, start_after: bool = False) -> None:
        try:
            port = assign_new_port(self.config_data, name)
            save_config(self.config_data, self.config_path)
            self.load_config()
            self.status_message.set(f"{name} now uses http://localhost:{port}.")
            if start_after:
                self.manager.start(name)
        except Exception as exc:
            self.status_message.set(str(exc))

    def stop_conflicting_program(self, name: str) -> None:
        runner = self.manager.runners.get(name)
        pid = runner.state.conflict_pid if runner else ""
        if not pid:
            self.status_message.set("I could not identify the program using that address.")
            return
        label = process_name(pid) or "the other program"
        if messagebox.askyesno(APP_NAME, f"Stop {label} so this project can start?"):
            kill_process_tree(int(pid))
            self.status_message.set(f"Stopped {label}. Try starting {name} again.")

    def show_logs(self, name: str) -> None:
        LogWindow(self, self.manager.runners[name])

    def open_browser(self, project: ProjectConfig) -> None:
        if project.url:
            import webbrowser

            webbrowser.open(project.url)

    def open_folder(self, project: ProjectConfig) -> None:
        folder = Path(project.folder)
        if folder.exists():
            subprocess.Popen(["explorer", str(folder)])
        else:
            self.status_message.set("This project's folder can't be found. Use Edit to fix the path.")

    def open_config_file(self) -> None:
        if self.config_path.exists():
            os.startfile(str(self.config_path))

    def toggle_startup(self) -> None:
        enabled = self.startup_enabled.get()
        try:
            set_startup_enabled(enabled)
            self.config_data.settings["start_on_windows_login"] = enabled
            save_config(self.config_data, self.config_path)
            self.status_message.set("Windows startup setting updated.")
        except Exception:
            logging.exception("Failed to update startup setting")
            self.status_message.set("Windows would not let me change the startup setting.")

    def _on_log(self, _name: str, _line: str) -> None:
        pass

    def _on_state(self, name: str, status: str, message: str) -> None:
        self.after(0, lambda: self._apply_state(name, status, message))

    def _apply_state(self, name: str, status: str, message: str) -> None:
        card = self.cards.get(name)
        runner = self.manager.runners.get(name)
        project = runner.project if runner else next((item for item in self.config_data.projects if item.name == name), None)
        if card and project:
            running = status in {"Starting", "Running"}
            card["status"].configure(text=self._status_text(status, project), bg=self._status_bg(status), fg=self._status_color(status))
            card["primary"].configure(
                text="Stop" if running else "Start",
                bg=RED if running else GREEN,
                fg="#ffffff",
                command=lambda n=name: self.toggle_project(n),
            )
            card["browser"].pack_forget()
            if running and project.url:
                card["browser"].pack(side="left", padx=10)
            card["url"].configure(text=project.url if running and project.url else "")
            self._render_runtime_issue(project, runner)
        if message:
            self.status_message.set(message)

    def _render_runtime_issue(self, project: ProjectConfig, runner) -> None:
        card = self.cards.get(project.name)
        if not card:
            return
        issue = card["issue"]
        for child in issue.winfo_children():
            child.destroy()
        if runner and runner.state.status == "Error" and runner.state.error_kind == "port_conflict":
            box = tk.Frame(issue, bg=SOFT_RED, padx=10, pady=8)
            box.pack(fill="x")
            tk.Label(box, text="Something else is already using this project's address.", bg=SOFT_RED, fg=RED).pack(anchor="w")
            actions = tk.Frame(box, bg=SOFT_RED)
            actions.pack(fill="x", pady=(8, 0))
            make_button(actions, "Use a free port instead", lambda n=project.name: self.assign_new_port_and_save(n, start_after=True), bg="#ffffff", fg=RED, padx=10, pady=5).pack(side="left")
            make_button(actions, "Stop the other program", lambda n=project.name: self.stop_conflicting_program(n), bg="#ffffff", fg=RED, padx=10, pady=5).pack(side="left", padx=8)
            make_button(actions, "Details", lambda r=runner: messagebox.showinfo(APP_NAME, r.state.details or "No details."), bg="#ffffff", fg=MUTED, padx=10, pady=5).pack(side="left")
        elif runner and runner.state.status == "Error":
            box = tk.Frame(issue, bg=SOFT_RED, padx=10, pady=8)
            box.pack(fill="x")
            tk.Label(box, text=runner.state.message or "This project did not start.", bg=SOFT_RED, fg=RED).pack(anchor="w")
            actions = tk.Frame(box, bg=SOFT_RED)
            actions.pack(fill="x", pady=(8, 0))
            make_button(actions, "Try again", lambda n=project.name: self.manager.start(n), bg="#ffffff", fg=RED, padx=10, pady=5).pack(side="left")
            make_button(actions, "View logs", lambda n=project.name: self.show_logs(n), bg="#ffffff", fg=RED, padx=10, pady=5).pack(side="left", padx=8)
        else:
            duplicates = duplicate_ports(self.config_data.projects)
            self._render_card_issues(project, project.port in duplicates)

    @staticmethod
    def _status_text(status: str, project: ProjectConfig) -> str:
        if status == "Starting":
            return "● Starting..."
        if status == "Running":
            return f"● Running on port {project.port}" if project.port else "● Running"
        if status == "Error":
            return "● Problem"
        return "● Stopped"

    @staticmethod
    def _status_bg(status: str) -> str:
        return {
            "Stopped": "#eceff1",
            "Starting": SOFT_YELLOW,
            "Running": SOFT_GREEN,
            "Error": SOFT_RED,
        }.get(status, "#eceff1")

    @staticmethod
    def _status_color(status: str) -> str:
        return {
            "Stopped": MUTED,
            "Starting": YELLOW,
            "Running": GREEN,
            "Error": RED,
        }.get(status, MUTED)

    def on_close(self) -> None:
        running = self.manager.running_names()
        if running:
            prompt = "These projects are still running:\n\n" + "\n".join(running) + "\n\nStop them before closing?"
            if messagebox.askyesno(APP_NAME, prompt):
                self.manager.stop_all()
            else:
                self.manager.stop_all(leave_running=True)
                messagebox.showwarning(APP_NAME, "Those projects were left running. This launcher can no longer stop them.")
        self.destroy()


def main() -> None:
    app = LauncherApp()
    app.mainloop()
