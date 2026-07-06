from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


MAX_MIND_MAP_DEPTH = 3
MAX_MIND_MAP_CHILDREN = 8
TIMESTAMP_RE = re.compile(r"\[(?P<stamp>\d{1,2}:\d{2}(?::\d{2})?)\]")


@dataclass(frozen=True)
class SourceRef:
    label: str
    seconds: int
    snippet: str


def validate_mind_map(value: Any) -> dict:
    if not isinstance(value, dict):
        raise ValueError("Mind map must be an object")
    return _validate_node(value, depth=0, fallback_id="root")


def _validate_node(value: dict, depth: int, fallback_id: str) -> dict:
    if depth > MAX_MIND_MAP_DEPTH:
        raise ValueError("Mind map is too deep")
    label = str(value.get("label", "")).strip()
    if not label:
        raise ValueError("Every mind map node needs a label")
    note = str(value.get("note", "")).strip()
    source = value.get("source")
    source_ref = _validate_source_ref(source) if isinstance(source, dict) else None
    raw_children = value.get("children") or []
    if not isinstance(raw_children, list):
        raise ValueError("Mind map children must be a list")
    if len(raw_children) > MAX_MIND_MAP_CHILDREN:
        raw_children = raw_children[:MAX_MIND_MAP_CHILDREN]

    node = {
        "id": str(value.get("id") or fallback_id),
        "label": label[:90],
        "note": note[:180],
        "children": [
            _validate_node(child, depth + 1, f"{fallback_id}-{index}")
            for index, child in enumerate(raw_children, start=1)
            if isinstance(child, dict)
        ],
    }
    if source_ref:
        node["source"] = source_ref
    if depth == 0 and not node["children"]:
        raise ValueError("Mind map needs at least one branch")
    return node


def _validate_source_ref(value: dict) -> dict | None:
    label = str(value.get("label", "")).strip()
    seconds = value.get("seconds")
    if not label and seconds is None:
        return None
    try:
        seconds_int = max(0, int(seconds))
    except (TypeError, ValueError):
        seconds_int = timestamp_to_seconds(label) if label else 0
    return {"label": label or seconds_to_timestamp(seconds_int), "seconds": seconds_int}


def mind_map_to_outline(node: dict, depth: int = 0) -> str:
    validated = validate_mind_map(node) if depth == 0 else node
    prefix = "  " * depth + "- "
    note = f": {validated.get('note')}" if validated.get("note") else ""
    source = validated.get("source") or {}
    source_text = f" ({source.get('label')})" if source.get("label") else ""
    lines = [f"{prefix}{validated['label']}{note}{source_text}"]
    for child in validated.get("children", []):
        lines.append(mind_map_to_outline(child, depth + 1))
    return "\n".join(lines)


def transcript_segments(transcript: str) -> list[dict]:
    matches = list(TIMESTAMP_RE.finditer(transcript or ""))
    if not matches:
        return []
    segments = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(transcript)
        text = transcript[start:end].strip()
        if text:
            label = match.group("stamp")
            segments.append({"label": label, "seconds": timestamp_to_seconds(label), "text": text})
    return segments


def timestamp_to_seconds(value: str) -> int:
    parts = [int(part) for part in value.strip("[]").split(":")]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return 0


def seconds_to_timestamp(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    remainder = seconds % 60
    if hours:
        return f"{hours}:{minutes:02d}:{remainder:02d}"
    return f"{minutes}:{remainder:02d}"


def best_source_ref(text: str, transcript: str) -> dict | None:
    segments = transcript_segments(transcript)
    if not segments:
        return None
    terms = _keywords(text)
    if not terms:
        return None
    scored = []
    for segment in segments:
        lower = segment["text"].lower()
        score = sum(lower.count(term) for term in terms)
        if score:
            scored.append((score, segment))
    if not scored:
        return None
    _score, segment = sorted(scored, key=lambda item: (-item[0], item[1]["seconds"]))[0]
    return {"label": segment["label"], "seconds": segment["seconds"], "snippet": segment["text"][:180]}


def key_point_citations(key_points: str, transcript: str) -> list[dict]:
    citations = []
    for line in (key_points or "").splitlines():
        text = line.strip().lstrip("-*0123456789. ").strip()
        if not text:
            continue
        source = best_source_ref(text, transcript)
        citations.append({"text": text, "source": source})
    return citations


def enrich_mind_map_sources(node: dict, transcript: str) -> dict:
    validated = validate_mind_map(node)

    def enrich(item: dict) -> dict:
        copy = {**item}
        if "source" not in copy:
            source = best_source_ref(f"{copy.get('label', '')} {copy.get('note', '')}", transcript)
            if source:
                copy["source"] = {"label": source["label"], "seconds": source["seconds"]}
        copy["children"] = [enrich(child) for child in copy.get("children", [])]
        return copy

    return enrich(validated)


def validate_script_sections(value: Any) -> list[dict]:
    if not isinstance(value, list):
        raise ValueError("Script must be a list of sections")
    sections = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Section {index} is not an object")
        title = str(item.get("title", "")).strip()
        narration = str(item.get("narration", "")).strip()
        if not title or not narration:
            raise ValueError(f"Section {index} needs title and narration")
        sections.append(
            {
                "title": title[:120],
                "duration": str(item.get("duration", "1 min")).strip() or "1 min",
                "narration": narration,
                "visuals": str(item.get("visuals", "")).strip(),
                "source": str(item.get("source", "")).strip(),
            }
        )
    if not sections:
        raise ValueError("Script needs at least one section")
    return sections


def script_sections_to_markdown(title: str, sections: list[dict], intro_note: str) -> str:
    parts = [f"# {title}", "", intro_note, ""]
    for section in validate_script_sections(sections):
        parts.extend(
            [
                f"## {section['title']}",
                "",
                f"Estimated duration: {section['duration']}",
                "",
                "Narration:",
                "",
                section["narration"],
                "",
            ]
        )
        if section.get("visuals"):
            parts.extend(["Visual suggestions:", "", section["visuals"], ""])
        if section.get("source"):
            parts.extend(["Source note:", "", section["source"], ""])
    return "\n".join(parts).strip() + "\n"


def revision_plan_text(weak_topics: list[dict], recommendations: list[dict]) -> str:
    if weak_topics:
        lines = ["Focus first on:"]
        for topic in weak_topics[:5]:
            lines.append(f"- {topic.get('topic')}: {topic.get('reason', 'Review this next.')}")
        return "\n".join(lines)
    if recommendations:
        lines = ["Suggested next steps:"]
        for item in recommendations[:5]:
            lines.append(f"- {item.get('title')}: {item.get('reason')}")
        return "\n".join(lines)
    return "Take a quiz or mark flashcards to build a personalized revision plan."


def export_sections(session: dict, options: dict | None = None) -> list[tuple[str, str]]:
    options = {
        "include_transcript": True,
        "include_quiz": True,
        "include_flashcards": True,
        "include_mind_map": True,
        **(options or {}),
    }
    sections: list[tuple[str, str]] = []
    _add(sections, "Short Summary", session.get("short_summary"))
    _add(sections, "Detailed Notes", session.get("detailed_summary") or session.get("summary"))
    _add(sections, "Lesson Breakdown", session.get("lesson_breakdown"))
    _add(sections, "Key Points", session.get("key_points"))
    _add(sections, "Important Terms and Definitions", session.get("terms"))
    if options["include_mind_map"] and session.get("mind_map"):
        _add(sections, "Mind Map Outline", mind_map_to_outline(session["mind_map"]))
    if options["include_quiz"]:
        _add(sections, "Quiz", session.get("quiz"))
    if options["include_flashcards"]:
        cards = session.get("flashcards") or []
        if cards:
            _add(sections, "Flashcards", _flashcards_text(cards))
    _add(sections, "Recommended Revision Plan", session.get("revision_plan"))
    if options["include_transcript"]:
        _add(sections, "Full Transcript", session.get("transcript"))
    return sections


def _add(sections: list[tuple[str, str]], heading: str, body: Any) -> None:
    text = str(body or "").strip()
    if text and text.lower() not in {"none created yet.", "none mentioned."}:
        sections.append((heading, text))


def _flashcards_text(cards: list[dict]) -> str:
    lines = []
    for index, card in enumerate(cards, start=1):
        lines.append(f"{index}. Front: {card.get('front', '')}\n   Back: {card.get('back', '')}")
    return "\n\n".join(lines)


def _keywords(text: str) -> set[str]:
    stop = {"the", "and", "for", "with", "this", "that", "from", "into", "your", "what", "when", "where"}
    return {
        term.lower()
        for term in re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", text or "")
        if term.lower() not in stop
    }
