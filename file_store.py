import re
import json
from pathlib import Path

import advanced_outputs
import exporter


BASE_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = BASE_DIR / "outputs"
TRANSCRIPTS_DIR = OUTPUTS_DIR / "transcripts"
SUMMARIES_DIR = OUTPUTS_DIR / "summaries"
PDFS_DIR = OUTPUTS_DIR / "pdfs"
COMBINED_DIR = OUTPUTS_DIR / "combined"


def ensure_output_dirs() -> None:
    for path in (TRANSCRIPTS_DIR, SUMMARIES_DIR, PDFS_DIR, COMBINED_DIR):
        path.mkdir(parents=True, exist_ok=True)


def _safe_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return cleaned[:80] or "lecture-notes"


def _base_name(session: dict) -> str:
    created = str(session.get("created_at", "")).replace(":", "").replace("T", "-")
    title = str(session.get("title", "session"))
    safe_title = _safe_part(title)
    if safe_title.startswith("session-"):
        return f"session-{int(session['id']):04d}-{created}"
    return f"session-{int(session['id']):04d}-{created}-{safe_title}"


def _write_text(path: Path, text: str) -> str:
    ensure_output_dirs()
    path.write_text(text, encoding="utf-8")
    return str(path.resolve())


def write_transcript(session: dict) -> str:
    body = "\n".join(
        [
            str(session.get("title", "Lecture Session")),
            f"Date: {session.get('created_at', '')}",
            "",
            "Full Transcript",
            "===============",
            "",
            str(session.get("transcript", "")),
            "",
        ]
    )
    return _write_text(TRANSCRIPTS_DIR / f"{_base_name(session)}.txt", body)


def write_summary(session: dict) -> str:
    body = build_markdown_export(session, {"include_transcript": False})
    return _write_text(SUMMARIES_DIR / f"{_base_name(session)}.md", body)


def write_combined(session: dict, options: dict | None = None) -> str:
    body = build_markdown_export(session, options)
    return _write_text(COMBINED_DIR / f"{_base_name(session)}.md", body)


def write_pdf(session: dict, options: dict | None = None) -> str:
    ensure_output_dirs()
    path = PDFS_DIR / f"{_base_name(session)}.pdf"
    path.write_bytes(exporter.generate_pdf(session, options=options))
    return str(path.resolve())


def write_outputs(session: dict, include_summary: bool = True, options: dict | None = None) -> dict:
    paths = {"transcript_path": write_transcript(session)}
    if include_summary:
        paths["summary_path"] = write_summary(session)
        paths["combined_path"] = write_combined(session, options)
        paths["pdf_path"] = write_pdf(session, options)
    return paths


def build_markdown_export(session: dict, options: dict | None = None) -> str:
    enriched = _enriched_session(session)
    lines = [
        f"# {enriched.get('title', 'Lecture Session')}",
        "",
        "## Lecture Details",
        "",
        f"- Lecture: {enriched.get('title', 'Lecture Session')}",
        f"- Module: {enriched.get('title', 'Lecture Session')}",
        f"- Date: {enriched.get('created_at', '')}",
        f"- Source: {enriched.get('source_type', 'recorded')}",
        f"- Duration: {enriched.get('duration_seconds', 0)} seconds",
        "",
    ]
    for heading, body in advanced_outputs.export_sections(enriched, options):
        lines.extend([f"## {heading}", "", body, ""])
    return "\n".join(lines).strip() + "\n"


def _enriched_session(session: dict) -> dict:
    enriched = dict(session)
    if "mind_map" not in enriched and enriched.get("mind_map_json"):
        try:
            enriched["mind_map"] = advanced_outputs.validate_mind_map(json.loads(enriched["mind_map_json"]))
        except Exception:
            enriched["mind_map"] = None
    if not enriched.get("lesson_breakdown") and enriched.get("mind_map"):
        enriched["lesson_breakdown"] = advanced_outputs.mind_map_to_outline(enriched["mind_map"])
    if not enriched.get("revision_plan"):
        enriched["revision_plan"] = advanced_outputs.revision_plan_text(
            enriched.get("weak_topics") or [],
            enriched.get("recommendations") or [],
        )
    return enriched


def _flashcards_markdown(cards: list[dict]) -> str:
    if not cards:
        return "None created yet."
    lines = []
    for index, card in enumerate(cards, start=1):
        lines.extend(
            [
                f"{index}. Front: {card.get('front', '')}",
                f"   Back: {card.get('back', '')}",
                f"   Topic: {card.get('topic', 'General')}",
                "",
            ]
        )
    return "\n".join(lines).strip()
