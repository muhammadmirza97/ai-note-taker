import json
import logging
import re
import urllib.error
import urllib.request

from summariser import _summarise_with_sumy


OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:1b"
CHUNK_SIZE = 12000


PROMPT_TEMPLATE = """You are a lab reflection assistant for a student working independently.
Use only facts that are present in the transcript, marker notes, or OCR text from screen frames.
Do not invent exact commands, file names, websites, results, or teacher explanations.
If something is unclear, say it is unclear.

The student needs a practical revision guide after finishing a lab session.

Return these sections:
1. Lab objective
2. What happened step by step
3. Tools, files, commands, or settings mentioned
4. Errors, blockers, or retry moments
5. Key concepts learned
6. Cleaner walkthrough to repeat next time
7. Things to revise

Transcript:
<transcript>
{transcript}
</transcript>

Markers:
<markers>
{markers}
</markers>

OCR text from screen frames:
<ocr_text>
{ocr_text}
</ocr_text>

Screen frame count: {frame_count}
"""


def _ollama_generate(prompt: str) -> str:
    payload = json.dumps(
        {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            if response.status != 200:
                raise RuntimeError(f"Ollama returned status {response.status}")
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError("Ollama request failed") from exc

    notes = str(data.get("response", "")).strip()
    if not notes:
        raise ValueError("Ollama returned an empty response")
    return notes


def _split_text(text: str, max_chars: int = CHUNK_SIZE) -> list[str]:
    paragraphs = [part.strip() for part in text.splitlines() if part.strip()]
    if not paragraphs:
        paragraphs = [text]

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            sentences = re.split(r"(?<=[.!?])\s+", paragraph)
            for sentence in sentences:
                if current and len(current) + len(sentence) + 1 > max_chars:
                    chunks.append(current.strip())
                    current = ""
                current += (" " if current else "") + sentence
            continue

        if current and len(current) + len(paragraph) + 2 > max_chars:
            chunks.append(current.strip())
            current = ""
        current += ("\n\n" if current else "") + paragraph

    if current.strip():
        chunks.append(current.strip())
    return chunks


def _format_markers(markers: list[dict]) -> str:
    if not markers:
        return "None recorded."

    lines = []
    for marker in markers:
        elapsed = int(marker.get("elapsed_seconds") or 0)
        note = str(marker.get("note") or "Marker")
        lines.append(f"{elapsed // 60}:{elapsed % 60:02d} - {note}")
    return "\n".join(lines)


def _fallback_breakdown(transcript: str, markers: list[dict], frame_count: int, ocr_text: str = "") -> str:
    marker_text = _format_markers(markers)
    if not transcript.strip() and not ocr_text.strip():
        return "\n".join(
            [
                "1. Lab objective",
                "Unclear from audio. The screen recording was saved for review.",
                "",
                "2. What happened step by step",
                "No speech was detected, so the app cannot reliably infer the steps yet.",
                "",
                "3. Tools, files, commands, or settings mentioned",
                "None mentioned.",
                "",
                "4. Errors, blockers, or retry moments",
                marker_text if markers else "None mentioned.",
                "",
                "5. Key concepts learned",
                "Unclear from audio.",
                "",
                "6. Cleaner walkthrough to repeat next time",
                "Review the saved screen recording and extracted frames. For stronger notes next time, narrate each major action briefly.",
                "",
                "7. Things to revise",
                f"Review the saved recording and {frame_count} extracted screen frames.",
            ]
        )

    source_text = "\n\n".join(part for part in [transcript.strip(), ocr_text.strip()] if part)
    summary = _summarise_with_sumy(source_text)
    return "\n".join(
        [
            "1. Lab objective",
            "Unclear unless stated in the transcript or visible screen text.",
            "",
            "2. What happened step by step",
            summary,
            "",
            "3. Tools, files, commands, or settings mentioned",
            "Review the transcript and OCR text below for exact names and values.",
            "",
            "4. Errors, blockers, or retry moments",
            marker_text if markers else "None mentioned.",
            "",
            "5. Key concepts learned",
            "Review the extracted notes and transcript.",
            "",
            "6. Cleaner walkthrough to repeat next time",
            "Use the transcript and screen frames to rebuild the exact steps.",
            "",
            "7. Things to revise",
            f"Review the saved recording and {frame_count} extracted screen frames.",
        ]
    )


def summarise_lab(transcript: str, markers: list[dict], frame_count: int, ocr_text: str = "") -> str:
    marker_text = _format_markers(markers)
    cleaned = "\n\n".join(part for part in [transcript.strip(), ocr_text.strip()] if part)
    if not cleaned and not markers:
        return _fallback_breakdown(transcript, markers, frame_count, ocr_text)

    chunks = _split_text(cleaned or "No speech detected.")
    try:
        if len(chunks) == 1:
            return _ollama_generate(
                PROMPT_TEMPLATE.format(
                    transcript=chunks[0],
                    markers=marker_text,
                    ocr_text=ocr_text[:CHUNK_SIZE],
                    frame_count=frame_count,
                )
            )

        partials = []
        for index, chunk in enumerate(chunks, start=1):
            prompt = (
                f"This is transcript part {index} of {len(chunks)}. Create lab step notes for this part only.\n\n"
                + PROMPT_TEMPLATE.format(
                    transcript=chunk,
                    markers=marker_text,
                    ocr_text=ocr_text[:CHUNK_SIZE],
                    frame_count=frame_count,
                )
            )
            partials.append(f"Part {index}\n{_ollama_generate(prompt)}")

        combined = "\n\n".join(partials)
        final_prompt = """Combine these lab notes into one practical revision guide.
Remove repeated points and preserve uncertainty where the transcript is unclear.

<part_notes>
{notes}
</part_notes>
""".format(notes=combined[:CHUNK_SIZE])
        return _ollama_generate(final_prompt)
    except Exception:
        logging.info("Lab Ollama summarisation unavailable; using fallback", exc_info=True)
        return _fallback_breakdown(transcript, markers, frame_count, ocr_text)
