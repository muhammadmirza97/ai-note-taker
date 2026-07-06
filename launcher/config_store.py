import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from launcher.readiness import infer_port_from_url, is_port_open
from launcher.resources import resource_path


APP_DIR_NAME = "ProjectLauncher"
CONFIG_NAME = "projects.json"
DEFAULT_PORT_START = 8100
DEFAULT_PORT_END = 8199


@dataclass
class ProjectConfig:
    name: str
    folder: str
    setup: list[str] = field(default_factory=list)
    run: str = ""
    url: str = ""
    port: int | None = None
    wants_browser: bool = True
    readiness: dict[str, Any] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)
    shell: str = "cmd"
    accent: str = "#276a61"


@dataclass
class LauncherConfig:
    settings: dict[str, Any] = field(default_factory=lambda: {
        "write_logs": True,
        "start_on_windows_login": False,
        "minimize_to_tray": False,
        "port_range_start": DEFAULT_PORT_START,
        "port_range_end": DEFAULT_PORT_END,
    })
    projects: list[ProjectConfig] = field(default_factory=list)


def app_data_dir() -> Path:
    root = os.environ.get("APPDATA")
    if root:
        return Path(root) / APP_DIR_NAME
    return Path.home() / f".{APP_DIR_NAME.lower()}"


def default_config_path() -> Path:
    return app_data_dir() / CONFIG_NAME


def bundled_example_path() -> Path:
    return resource_path("projects.example.json")


def ensure_config(path: Path | None = None) -> Path:
    target = path or default_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        save_config(default_config(), target)
    return target


def default_config() -> LauncherConfig:
    return LauncherConfig(
        settings={
            "write_logs": True,
            "start_on_windows_login": False,
            "minimize_to_tray": False,
            "port_range_start": DEFAULT_PORT_START,
            "port_range_end": DEFAULT_PORT_END,
        },
        projects=[],
    )


def _project_from_dict(raw: dict[str, Any]) -> ProjectConfig:
    port_value = raw.get("port")
    port = None
    if str(port_value).lower() not in {"", "none", "auto"}:
        try:
            port = int(port_value)
        except Exception:
            port = None
    return ProjectConfig(
        name=str(raw.get("name", "")).strip(),
        folder=str(raw.get("folder", "")).strip(),
        setup=[str(item) for item in raw.get("setup", []) if str(item).strip()],
        run=str(raw.get("run", "")).strip(),
        url=str(raw.get("url", "")).strip(),
        port=port,
        wants_browser=bool(raw.get("wants_browser", True)),
        readiness=dict(raw.get("readiness") or {}),
        env={str(k): str(v) for k, v in dict(raw.get("env") or {}).items()},
        shell=str(raw.get("shell") or "cmd").strip().lower(),
        accent=str(raw.get("accent") or "#276a61").strip(),
    )


def load_config(path: Path | None = None) -> LauncherConfig:
    config_path = ensure_config(path)
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Config file has invalid JSON near line {exc.lineno}: {exc.msg}") from exc
    if not isinstance(raw, dict):
        raise ValueError("Config must be a JSON object with settings and projects.")
    settings = dict(raw.get("settings") or {})
    base_settings = LauncherConfig().settings
    base_settings.update(settings)
    projects = [_project_from_dict(item) for item in raw.get("projects", []) if isinstance(item, dict)]
    config = LauncherConfig(settings=base_settings, projects=projects)
    normalize_project_urls(config)
    return config


def save_config(config: LauncherConfig, path: Path | None = None) -> None:
    target = path or default_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "settings": config.settings,
        "projects": [asdict(project) for project in config.projects],
    }
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def readiness_for(project: ProjectConfig) -> dict[str, Any]:
    readiness = dict(project.readiness or {})
    kind = str(readiness.get("type") or "").lower()
    if not kind:
        inferred_port = project.port or infer_port_from_url(project.url)
        if inferred_port:
            readiness = {"type": "port", "port": inferred_port, "timeout_seconds": 60}
        else:
            readiness = {"type": "none", "timeout_seconds": 0}
    if "timeout_seconds" not in readiness:
        readiness["timeout_seconds"] = 60
    return readiness


def validate_project(project: ProjectConfig) -> list[str]:
    errors: list[str] = []
    label = project.name or "Unnamed project"
    if not project.name:
        errors.append("Project name is required.")
    if not project.folder:
        errors.append(f"Project '{label}': folder is required.")
    elif not Path(project.folder).exists():
        errors.append(f"Project '{label}': folder does not exist - check the path in settings.")
    elif not Path(project.folder).is_dir():
        errors.append(f"Project '{label}': folder must be a directory.")
    if not project.run:
        errors.append(f"Project '{label}': run command is required.")
    if project.port is not None and not (1 <= int(project.port) <= 65535):
        errors.append(f"Project '{label}': port must be between 1 and 65535.")
    if project.shell not in {"cmd", "powershell"}:
        errors.append(f"Project '{label}': shell must be cmd or powershell.")

    readiness = readiness_for(project)
    kind = str(readiness.get("type") or "none").lower()
    if kind not in {"none", "port", "output"}:
        errors.append(f"Project '{label}': readiness type must be none, port, or output.")
    if kind == "port":
        try:
            port = int(readiness.get("port"))
            if port < 1 or port > 65535:
                raise ValueError
        except Exception:
            errors.append(f"Project '{label}': readiness port must be between 1 and 65535.")
    if kind == "output" and not str(readiness.get("text", "")).strip():
        errors.append(f"Project '{label}': output readiness needs text to match.")
    return errors


def validate_config(config: LauncherConfig) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    duplicates = duplicate_ports(config.projects)
    for project in config.projects:
        errors = validate_project(project)
        if project.port in duplicates:
            errors.append(f"Project '{project.name}': this port is already used by another project.")
        if errors:
            result[project.name or "Unnamed project"] = errors
    return result


def port_range(config: LauncherConfig) -> tuple[int, int]:
    start = int(config.settings.get("port_range_start") or DEFAULT_PORT_START)
    end = int(config.settings.get("port_range_end") or DEFAULT_PORT_END)
    if start > end:
        start, end = end, start
    return start, end


def duplicate_ports(projects: list[ProjectConfig]) -> set[int]:
    seen: set[int] = set()
    duplicates: set[int] = set()
    for project in projects:
        if project.port is None:
            continue
        if project.port in seen:
            duplicates.add(project.port)
        seen.add(project.port)
    return duplicates


def used_ports(projects: list[ProjectConfig], exclude_name: str = "") -> set[int]:
    return {
        int(project.port)
        for project in projects
        if project.port is not None and project.name != exclude_name
    }


def find_free_port(config: LauncherConfig, exclude_name: str = "") -> int:
    start, end = port_range(config)
    reserved = used_ports(config.projects, exclude_name=exclude_name)
    for port in range(start, end + 1):
        if port not in reserved and not is_port_open(port):
            return port
    raise ValueError(f"No free ports are available in {start}-{end}.")


def apply_project_port(project: ProjectConfig, port: int) -> ProjectConfig:
    project.port = int(port)
    if project.wants_browser:
        project.url = f"http://localhost:{int(port)}"
    project.readiness = {"type": "port", "port": int(port), "timeout_seconds": int(project.readiness.get("timeout_seconds", 60) if project.readiness else 60)}
    return project


def assign_missing_ports(config: LauncherConfig) -> bool:
    changed = False
    for project in config.projects:
        if project.port is None:
            apply_project_port(project, find_free_port(config, exclude_name=project.name))
            changed = True
    return changed


def drop_broken_sample_projects(config: LauncherConfig) -> bool:
    if not config.projects:
        return False
    if all(project.name.lower().startswith("sample") and not Path(project.folder).exists() for project in config.projects):
        config.projects = []
        return True
    return False


def assign_new_port(config: LauncherConfig, project_name: str) -> int:
    for project in config.projects:
        if project.name == project_name:
            port = find_free_port(config, exclude_name=project_name)
            apply_project_port(project, port)
            return port
    raise KeyError(project_name)


def normalize_project_urls(config: LauncherConfig) -> None:
    for project in config.projects:
        if project.port is None:
            inferred = infer_port_from_url(project.url)
            if inferred:
                project.port = inferred
        if project.port and project.wants_browser and not project.url:
            project.url = f"http://localhost:{project.port}"


def project_from_registration(raw: dict[str, Any], config: LauncherConfig) -> ProjectConfig:
    project = _project_from_dict(
        {
            "name": raw.get("name", ""),
            "folder": raw.get("folder", ""),
            "setup": raw.get("setup", []),
            "run": raw.get("run", ""),
            "wants_browser": raw.get("wants_browser", True),
            "port": raw.get("port", "auto"),
            "shell": raw.get("shell", "cmd"),
            "env": raw.get("env", {}),
        }
    )
    if project.port is None:
        project.port = find_free_port(config)
    apply_project_port(project, project.port)
    return project
