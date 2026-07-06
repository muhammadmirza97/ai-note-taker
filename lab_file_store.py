import re
from pathlib import Path

import lab_exporter


BASE_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = BASE_DIR / "outputs" / "labs"
RECORDINGS_DIR = OUTPUTS_DIR / "recordings"
FRAMES_DIR = OUTPUTS_DIR / "frames"
TRANSCRIPTS_DIR = OUTPUTS_DIR / "transcripts"
BREAKDOWNS_DIR = OUTPUTS_DIR / "breakdowns"
COMBINED_DIR = OUTPUTS_DIR / "combined"
PDFS_DIR = OUTPUTS_DIR / "pdfs"


def ensure_output_dirs() -> None:
    for path in (
        OUTPUTS_DIR,
        RECORDINGS_DIR,
        FRAMES_DIR,
        TRANSCRIPTS_DIR,
        BREAKDOWNS_DIR,
        COMBINED_DIR,
        PDFS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)


def _safe_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return cleaned[:80] or "lab-session"


def _base_name(session: dict) -> str:
    created = str(session.get("created_at", "")).replace(":", "").replace("T", "-")
    title = str(session.get("title", "lab-session"))
    safe_title = _safe_part(title)
    if safe_title.startswith("lab-session"):
        return f"lab-session-{int(session['id']):04d}-{created}"
    return f"lab-session-{int(session['id']):04d}-{created}-{safe_title}"


def _write_text(path: Path, text: str) -> str:
    ensure_output_dirs()
    path.write_text(text, encoding="utf-8")
    return str(path.resolve())


def write_transcript(session: dict) -> str:
    body = "\n".join(
        [
            str(session.get("title", "Lab Session")),
            f"Date: {session.get('created_at', '')}",
            f"Recording: {session.get('recording_path', '')}",
            "",
            "Transcript",
            "==========",
            "",
            str(session.get("transcript", "")),
            "",
        ]
    )
    return _write_text(TRANSCRIPTS_DIR / f"{_base_name(session)}.txt", body)


def write_breakdown(session: dict) -> str:
    body = "\n".join(
        [
            f"# {session.get('title', 'Lab Session')}",
            "",
            f"Date: {session.get('created_at', '')}",
            f"Recording: {session.get('recording_path', '')}",
            "",
            "## Lab Breakdown",
            "",
            str(session.get("breakdown", "")),
            "",
            "## Screen Text",
            "",
            str(session.get("ocr_text", "")).strip() or "None detected or OCR unavailable.",
            "",
        ]
    )
    return _write_text(BREAKDOWNS_DIR / f"{_base_name(session)}.md", body)


def write_combined(session: dict) -> str:
    markers = session.get("markers") or []
    marker_lines = []
    for marker in markers:
        elapsed = int(marker.get("elapsed_seconds") or 0)
        note = str(marker.get("note") or "Marker")
        marker_lines.append(f"- {elapsed // 60}:{elapsed % 60:02d} - {note}")

    frames = session.get("frames") or []
    frame_lines = [f"- {path}" for path in frames]

    body = "\n".join(
        [
            f"# {session.get('title', 'Lab Session')}",
            "",
            f"Date: {session.get('created_at', '')}",
            f"Duration: {session.get('duration_seconds', 0)} seconds",
            f"Recording: {session.get('recording_path', '')}",
            "",
            "## Lab Breakdown",
            "",
            str(session.get("breakdown", "")),
            "",
            "## Markers",
            "",
            "\n".join(marker_lines) if marker_lines else "None recorded.",
            "",
            "## Screen Text",
            "",
            str(session.get("ocr_text", "")).strip() or "None detected or OCR unavailable.",
            "",
            "## Screen Frames",
            "",
            "\n".join(frame_lines) if frame_lines else "None extracted.",
            "",
            "## Transcript",
            "",
            str(session.get("transcript", "")),
            "",
        ]
    )
    return _write_text(COMBINED_DIR / f"{_base_name(session)}.md", body)


def write_pdf(session: dict) -> str:
    ensure_output_dirs()
    path = PDFS_DIR / f"{_base_name(session)}.pdf"
    path.write_bytes(lab_exporter.generate_pdf(session))
    return str(path.resolve())


def write_outputs(session: dict, include_breakdown: bool = True) -> dict:
    paths = {"transcript_path": write_transcript(session)}
    if include_breakdown:
        paths["breakdown_path"] = write_breakdown(session)
        paths["combined_path"] = write_combined(session)
        paths["pdf_path"] = write_pdf(session)
    return paths
