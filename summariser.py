import logging
import json
import os
import re
import urllib.error
import urllib.request

from sumy.nlp.tokenizers import Tokenizer
from sumy.parsers.plaintext import PlaintextParser
from sumy.summarizers.lsa import LsaSummarizer

import study_intelligence
import advanced_outputs


OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
CHUNK_SIZE = 12000


GROUNDING_INSTRUCTION = """Use only information present in the transcript or uploaded text.
If something is unclear or missing, say so instead of inventing details."""


PROMPT_TEMPLATE = """You are a lecture notes assistant. A lecture transcript is provided inside <transcript> tags.
Do not say that no transcript was provided. If the transcript is short, still produce useful study notes from it.
Use only facts explicitly present in the transcript. Do not invent dates, reports, figures, examples, or fictional lecture content.
If a requested section has no information in the transcript, write "None mentioned."

Given the following lecture transcript, extract:
1. The main topic
2. Key concepts and definitions (bullet points)
3. Important facts or figures mentioned
4. Any action items or things to remember

<transcript>
{transcript}
</transcript>

Provide clear, concise notes a student can study from."""


GENERATION_PROMPTS = {
    "short_summary": """Write a short summary in 3 to 5 plain-language sentences.
Focus on the most important ideas a student should remember.""",
    "detailed_summary": """Write detailed study notes with clear Markdown headings.
Use short sections, concise paragraphs, and include only ideas grounded in the source.""",
    "key_points": """Create a concise bullet list of the most important ideas.
Each bullet should be one useful study point and avoid repetition.""",
    "terms": """List important terms and one-line definitions.
Use the format "- Term: definition". If no terms are clearly defined, write "None mentioned.".""",
    "quiz": """Create 5 to 10 multiple-choice questions grounded strictly in the source.
Use this Markdown format for each question:
1. Question text
   A. Option
   B. Option
   C. Option
   D. Option
   Answer: Letter - brief explanation
If the source is too short for 5 questions, create as many useful questions as it supports.""",
}


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
        with urllib.request.urlopen(request, timeout=60) as response:
            if response.status != 200:
                raise RuntimeError(f"Ollama returned status {response.status}")
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError("Ollama request failed") from exc

    notes = str(data.get("response", "")).strip()
    if not notes:
        raise ValueError("Ollama returned an empty response")
    lower_notes = notes.lower()
    bad_response_phrases = (
        "no actual transcript provided",
        "no lecture transcript provided",
        "no transcript provided",
        "please share the transcript",
        "provide the lecture transcript",
        "fictional one",
        "fictional transcript",
        "for demonstration purposes",
    )
    if any(phrase in lower_notes for phrase in bad_response_phrases):
        raise ValueError("Ollama did not use the provided transcript")
    return notes


def _extract_json(value: str):
    text = value.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start_candidates = [index for index in (text.find("["), text.find("{")) if index >= 0]
        if not start_candidates:
            raise
        start = min(start_candidates)
        end = max(text.rfind("]"), text.rfind("}"))
        if end <= start:
            raise
        return json.loads(text[start : end + 1])


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


def _select_relevant_chunks(transcript: str, question: str, max_chunks: int = 4) -> str:
    chunks = _split_text(transcript, max_chars=3500)
    if len(chunks) <= max_chunks:
        return "\n\n".join(chunks)

    terms = {
        term.lower()
        for term in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", question)
        if term.lower() not in {"the", "and", "for", "with", "this", "that", "what", "how", "why", "are", "you"}
    }

    scored = []
    for index, chunk in enumerate(chunks):
        lower = chunk.lower()
        score = sum(lower.count(term) for term in terms)
        scored.append((score, index, chunk))

    best = sorted(scored, key=lambda item: (-item[0], item[1]))[:max_chunks]
    return "\n\n".join(chunk for _score, _index, chunk in sorted(best, key=lambda item: item[1]))


def _has_timestamps(text: str) -> bool:
    return bool(re.search(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", text))


def _grounded_prompt(transcript: str, task: str) -> str:
    return f"""You are a careful lecture notes assistant for students.
{GROUNDING_INSTRUCTION}

Task:
{task}

<transcript>
{transcript}
</transcript>

Return only the requested study content. Do not include UI text."""


def _generate_grounded(transcript: str, task: str) -> str:
    chunks = _split_text(transcript)
    if len(chunks) == 1:
        return _ollama_generate(_grounded_prompt(transcript, task))

    partial_outputs: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        partial_outputs.append(
            f"Part {index}\n{_ollama_generate(_grounded_prompt(chunk, f'{task}\\nThis is part {index} of {len(chunks)}.'))}"
        )

    combined = "\n\n".join(partial_outputs)
    if len(combined) > CHUNK_SIZE:
        return combined

    return _ollama_generate(
        f"""You are combining grounded study notes from parts of one source.
{GROUNDING_INSTRUCTION}

Task:
{task}

<part_notes>
{combined}
</part_notes>

Return one clean final answer with duplicates removed."""
    )


def _json_generate_with_retry(prompt: str, validator) -> list[dict]:
    last_error: Exception | None = None
    for _attempt in range(2):
        try:
            raw = _ollama_generate(prompt)
            return validator(_extract_json(raw))
        except Exception as exc:
            last_error = exc
    raise ValueError("The AI returned an invalid structure") from last_error


def _json_object_generate_with_retry(prompt: str, validator) -> dict:
    last_error: Exception | None = None
    for _attempt in range(2):
        try:
            raw = _ollama_generate(prompt)
            return validator(_extract_json(raw))
        except Exception as exc:
            last_error = exc
    raise ValueError("The AI returned an invalid structure") from last_error


def _summarise_with_ollama(transcript: str) -> str:
    chunks = _split_text(transcript)
    if len(chunks) == 1:
        return _ollama_generate(PROMPT_TEMPLATE.format(transcript=transcript))

    partial_notes: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        prompt = (
            f"This is part {index} of {len(chunks)} of a long lecture transcript. "
            "Create concise bullet notes only for this part.\n\n"
            + PROMPT_TEMPLATE.format(transcript=chunk)
        )
        partial_notes.append(f"Part {index}\n{_ollama_generate(prompt)}")

    combined = "\n\n".join(partial_notes)
    if len(combined) > CHUNK_SIZE:
        return combined

    final_prompt = """You are a lecture notes assistant. Combine these part-by-part notes into one clean study guide.
Keep repeated points only once. Preserve important definitions, facts, examples, and action items.

<part_notes>
{notes}
</part_notes>

Return:
1. Main topic
2. Key concepts and definitions
3. Important facts or figures
4. Things to remember
""".format(notes=combined[:CHUNK_SIZE])
    try:
        return _ollama_generate(final_prompt)
    except Exception:
        return combined


def _summarise_with_sumy(transcript: str) -> str:
    cleaned = transcript.strip()
    if not cleaned:
        return "No speech was detected in the recording."

    try:
        parser = PlaintextParser.from_string(cleaned, Tokenizer("english"))
        summarizer = LsaSummarizer()
        sentences = summarizer(parser.document, 8)
        bullets = [f"- {sentence}" for sentence in sentences]
    except Exception:
        logging.info("Sumy summarisation failed; using sentence fallback", exc_info=True)
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned) if part.strip()]
        bullets = [f"- {sentence}" for sentence in sentences[:8]]

    if bullets:
        return "\n".join(bullets)
    return f"- {cleaned[:800]}"


def _sentences(transcript: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", transcript.strip()) if part.strip()]


def _fallback_short_summary(transcript: str) -> str:
    sentences = _sentences(transcript)
    if not sentences:
        return "No speech was detected in the recording."
    return " ".join(sentences[:5])


def _fallback_detailed_summary(transcript: str) -> str:
    summary = _summarise_with_sumy(transcript)
    return "\n".join(["## Main Ideas", "", summary])


def _fallback_key_points(transcript: str) -> str:
    sentences = _sentences(transcript)
    if not sentences:
        return "None mentioned."
    return "\n".join(f"- {sentence}" for sentence in sentences[:10])


def _fallback_terms(transcript: str) -> str:
    candidates = []
    for sentence in _sentences(transcript):
        if re.search(r"\b(is|are|means|refers to|called)\b", sentence, flags=re.IGNORECASE):
            candidates.append(sentence)
    if not candidates:
        return "None mentioned."
    return "\n".join(f"- {sentence}" for sentence in candidates[:8])


def _fallback_quiz(transcript: str) -> str:
    sentences = _sentences(transcript)
    if not sentences:
        return "None mentioned."
    questions = []
    for index, sentence in enumerate(sentences[:5], start=1):
        questions.append(
            "\n".join(
                [
                    f"{index}. Which point was mentioned in the lecture?",
                    f"   A. {sentence}",
                    "   B. A point not stated in the source",
                    "   C. A different unrelated topic",
                    "   D. None of the above",
                    "   Answer: A - This option repeats information from the transcript.",
                ]
            )
        )
    return "\n\n".join(questions)


FALLBACKS = {
    "short_summary": _fallback_short_summary,
    "detailed_summary": _fallback_detailed_summary,
    "key_points": _fallback_key_points,
    "terms": _fallback_terms,
    "quiz": _fallback_quiz,
}


def quiz_to_markdown(questions: list[dict]) -> str:
    validated = study_intelligence.validate_quiz_questions(questions)
    blocks = []
    for index, question in enumerate(validated, start=1):
        blocks.append(
            "\n".join(
                [
                    f"{index}. [{question['topic']}] {question['question']}",
                    f"   A. {question['options']['A']}",
                    f"   B. {question['options']['B']}",
                    f"   C. {question['options']['C']}",
                    f"   D. {question['options']['D']}",
                    f"   Answer: {question['answer']} - {question['explanation']}",
                ]
            )
        )
    return "\n\n".join(blocks)


def generate_quiz_questions(transcript: str, focus_topic: str = "", count: int = 8) -> list[dict]:
    if not transcript.strip():
        return []
    task = f"""Create {max(3, min(10, count))} multiple-choice questions as JSON only.
Each item must include: id, topic, question, options, answer, explanation.
The options field must be an object with A, B, C, D.
The answer field must be one letter: A, B, C, or D.
The topic must be a short label for the concept being tested.
{f'Focus only on this topic if the lecture supports it: {focus_topic}.' if focus_topic else ''}
Use only the source. If the source does not support a question, do not create it."""
    prompt = _grounded_prompt(transcript, task)
    try:
        return _json_generate_with_retry(prompt, study_intelligence.validate_quiz_questions)
    except Exception:
        sentences = _sentences(transcript)
        selected = sentences[: max(3, min(5, len(sentences)))]
        questions = []
        for index, sentence in enumerate(selected, start=1):
            questions.append(
                {
                    "id": f"q{index}",
                    "topic": focus_topic or "General",
                    "question": "Which point was mentioned in the lecture?",
                    "options": {
                        "A": sentence,
                        "B": "A point not stated in the lecture",
                        "C": "A different unrelated topic",
                        "D": "None of the above",
                    },
                    "answer": "A",
                    "explanation": "This option repeats information from the lecture.",
                }
            )
        return study_intelligence.validate_quiz_questions(questions)


def generate_flashcards(transcript: str) -> list[dict]:
    if not transcript.strip():
        return []
    word_count = len(transcript.split())
    count = 10 if word_count < 1200 else 15 if word_count < 3000 else 20
    task = f"""Create about {count} flashcards as JSON only.
Each item must include: front, back, topic.
Use a mix of term-definition, concept-explanation, and question-answer cards.
Keep the front short and the back useful for studying.
Use only the lecture content."""
    try:
        return _json_generate_with_retry(_grounded_prompt(transcript, task), study_intelligence.validate_flashcards)
    except Exception:
        cards = []
        for index, sentence in enumerate(_sentences(transcript)[:count], start=1):
            cards.append({"front": f"What was point {index}?", "back": sentence, "topic": "General"})
        return study_intelligence.validate_flashcards(cards) if cards else []


def answer_question(transcript: str, question: str, history: list[dict] | None = None) -> str:
    if not transcript.strip():
        return "This lecture does not have a transcript yet, so I cannot answer from it."
    context = _select_relevant_chunks(transcript, question)
    timestamp_instruction = (
        "If useful, cite the exact timestamp from the source, such as around 14:32."
        if _has_timestamps(context)
        else "Do not cite timestamps because this transcript does not include them."
    )
    history_text = "\n".join(
        f"{item.get('role', 'student')}: {item.get('content', '')}" for item in (history or [])[-8:]
    )
    prompt = f"""You are answering a student's question about one lecture.
{GROUNDING_INSTRUCTION}
If the answer is not covered, say "This wasn't covered in the lecture."
Be friendly, concise, and useful for studying.
{timestamp_instruction}

Recent conversation:
{history_text or 'None yet.'}

Student question:
{question}

Relevant lecture source:
<transcript>
{context}
</transcript>

Answer the student."""
    try:
        return _ollama_generate(prompt)
    except Exception:
        lowered = question.lower()
        if "important" in lowered or "study" in lowered:
            return _fallback_key_points(context)
        if "simpl" in lowered or "explain" in lowered:
            return _fallback_short_summary(context)
        return "I could not reach the local AI just now. The most relevant lecture text I found is:\n\n" + context[:900]


def generate_mind_map(transcript: str, title: str = "Lecture") -> dict:
    task = """Create a readable hierarchical mind map as JSON only.
The root object must include label, optional note, and children.
Use 4 to 8 main branches and 2 to 5 children each.
Each node may include source as {"label":"0:42","seconds":42} only if the transcript contains that timestamp.
Do not invent timestamps or content."""
    try:
        tree = _json_object_generate_with_retry(_grounded_prompt(transcript, task), advanced_outputs.validate_mind_map)
    except Exception:
        tree = _fallback_mind_map(transcript, title)
    return advanced_outputs.enrich_mind_map_sources(tree, transcript)


def _fallback_mind_map(transcript: str, title: str) -> dict:
    sentences = _sentences(transcript)
    branches = []
    for index, sentence in enumerate(sentences[:6], start=1):
        branches.append(
            {
                "id": f"b{index}",
                "label": f"Key idea {index}",
                "note": sentence[:150],
                "children": [],
            }
        )
    if not branches:
        branches = [{"id": "b1", "label": "Lecture content", "note": "No detailed transcript was available.", "children": []}]
    return advanced_outputs.validate_mind_map({"id": "root", "label": title, "note": "Lecture topic", "children": branches})


def generate_video_script(transcript: str, title: str = "Lecture") -> str:
    task = """Create a beginner-friendly learning video plan as JSON only.
Return a list of sections. Each section must include title, duration, narration, visuals, and source.
Include hook/intro, chapter-style sections, recap/outro.
Keep it ready to record or feed into a video tool. Use only source content."""
    try:
        sections = _json_generate_with_retry(_grounded_prompt(transcript, task), advanced_outputs.validate_script_sections)
    except Exception:
        sections = _fallback_script_sections(transcript)
    return advanced_outputs.script_sections_to_markdown(
        f"{title} - Learning Video Script",
        sections,
        "Ready to record or feed into a video tool. Script only; no video or audio is generated.",
    )


def generate_podcast_script(transcript: str, title: str = "Lecture", style: str = "two_voice") -> str:
    voice_instruction = (
        "Use HOST and ALEX as a warm two-voice dialogue."
        if style == "two_voice"
        else "Use one friendly narrator voice."
    )
    task = f"""Create a podcast-style script as JSON only.
Return a list of sections with title, duration, narration, visuals, and source.
{voice_instruction}
Structure it with cold open, main discussion, worked example or analogy, quick-fire recap, and outro.
Spoken language only in narration. Ground it in the lecture."""
    try:
        sections = _json_generate_with_retry(_grounded_prompt(transcript, task), advanced_outputs.validate_script_sections)
    except Exception:
        sections = _fallback_script_sections(transcript, podcast=True, two_voice=(style == "two_voice"))
    return advanced_outputs.script_sections_to_markdown(
        f"{title} - Podcast Script",
        sections,
        "Script only; no audio is generated.",
    )


def _fallback_script_sections(transcript: str, podcast: bool = False, two_voice: bool = True) -> list[dict]:
    sentences = _sentences(transcript)
    source = "Source: transcript"
    if advanced_outputs.transcript_segments(transcript):
        first = advanced_outputs.transcript_segments(transcript)[0]
        source = f"Source: around {first['label']}"
    if podcast and two_voice:
        narration = "HOST: Let's make this lecture easier to follow.\nALEX: Great. What's the first thing I should know?"
    else:
        narration = "Let's make this lecture easier to follow. We will start with the main ideas and end with what to review."
    return advanced_outputs.validate_script_sections(
        [
            {
                "title": "Intro",
                "duration": "1 min",
                "narration": narration,
                "visuals": "Show the lecture title and the main topic.",
                "source": source,
            },
            {
                "title": "Main ideas",
                "duration": "3-5 min",
                "narration": " ".join(sentences[:8]) or "No detailed transcript was available.",
                "visuals": "Show key terms and a simple diagram of the main relationships.",
                "source": source,
            },
            {
                "title": "Recap",
                "duration": "1 min",
                "narration": "Review the key points and choose one weak topic to study next.",
                "visuals": "Show a checklist of the key points.",
                "source": source,
            },
        ]
    )


def generate_output(transcript: str, kind: str) -> str:
    if not transcript.strip():
        return "No speech was detected in the recording."
    if kind not in GENERATION_PROMPTS:
        raise ValueError(f"Unsupported generation type: {kind}")

    try:
        return _generate_grounded(transcript, GENERATION_PROMPTS[kind])
    except Exception:
        logging.info("Ollama unavailable for %s; using fallback", kind, exc_info=True)
        return FALLBACKS[kind](transcript)


def generate_study_materials(transcript: str) -> dict[str, str]:
    return {
        "short_summary": generate_output(transcript, "short_summary"),
        "detailed_summary": generate_output(transcript, "detailed_summary"),
        "key_points": generate_output(transcript, "key_points"),
        "terms": generate_output(transcript, "terms"),
        "quiz": generate_output(transcript, "quiz"),
    }


def summarise(transcript: str) -> str:
    if not transcript.strip():
        return "No speech was detected in the recording."

    if len(transcript.split()) < 80:
        return _summarise_with_sumy(transcript)

    try:
        return generate_output(transcript, "detailed_summary")
    except Exception:
        logging.info("Ollama unavailable; using sumy fallback", exc_info=True)
        return _summarise_with_sumy(transcript)
