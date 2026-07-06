from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any


ANSWER_LETTERS = {"A", "B", "C", "D"}


def validate_quiz_questions(value: Any) -> list[dict]:
    if not isinstance(value, list):
        raise ValueError("Quiz must be a list of questions")

    validated = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Question {index} is not an object")
        question = str(item.get("question", "")).strip()
        topic = str(item.get("topic", "")).strip() or "General"
        explanation = str(item.get("explanation", "")).strip()
        options = item.get("options")
        answer = str(item.get("answer", "")).strip().upper()

        if not question:
            raise ValueError(f"Question {index} is missing text")
        if not isinstance(options, dict) or set(options.keys()) != ANSWER_LETTERS:
            raise ValueError(f"Question {index} must have A, B, C, and D options")
        clean_options = {letter: str(options[letter]).strip() for letter in sorted(ANSWER_LETTERS)}
        if any(not option for option in clean_options.values()):
            raise ValueError(f"Question {index} has an empty option")
        if answer not in ANSWER_LETTERS:
            raise ValueError(f"Question {index} has an invalid answer")

        validated.append(
            {
                "id": str(item.get("id") or f"q{index}"),
                "topic": topic[:80],
                "question": question,
                "options": clean_options,
                "answer": answer,
                "explanation": explanation or "This answer is grounded in the lecture.",
            }
        )

    if not validated:
        raise ValueError("Quiz must include at least one question")
    return validated


def validate_flashcards(value: Any) -> list[dict]:
    if not isinstance(value, list):
        raise ValueError("Flashcards must be a list")
    validated = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Flashcard {index} is not an object")
        front = str(item.get("front", "")).strip()
        back = str(item.get("back", "")).strip()
        topic = str(item.get("topic", "")).strip() or "General"
        if not front or not back:
            raise ValueError(f"Flashcard {index} needs a front and back")
        validated.append(
            {
                "front": front,
                "back": back,
                "topic": topic[:80],
            }
        )
    if not validated:
        raise ValueError("At least one flashcard is required")
    return validated


def score_quiz_attempt(questions: list[dict], answers: dict[str, str]) -> dict:
    validated = validate_quiz_questions(questions)
    results = []
    correct_count = 0
    for question in validated:
        selected = str(answers.get(question["id"], "")).strip().upper()
        correct = selected == question["answer"]
        if correct:
            correct_count += 1
        results.append(
            {
                "question_id": question["id"],
                "topic": question["topic"],
                "question": question["question"],
                "selected_answer": selected,
                "correct_answer": question["answer"],
                "is_correct": correct,
                "explanation": question["explanation"],
            }
        )

    total = len(validated)
    return {
        "score": correct_count,
        "total": total,
        "percent": round((correct_count / total) * 100) if total else 0,
        "results": results,
    }


def compute_weak_topics(attempts: list[dict], flashcards: list[dict] | None = None, limit: int = 5) -> list[dict]:
    stats: dict[str, dict[str, int]] = defaultdict(lambda: {"correct": 0, "total": 0, "not_yet": 0})

    for attempt in attempts:
        for result in attempt.get("results", []):
            topic = str(result.get("topic") or "General")
            stats[topic]["total"] += 1
            if result.get("is_correct"):
                stats[topic]["correct"] += 1

    for card in flashcards or []:
        if str(card.get("status", "")).lower() == "not_yet":
            topic = str(card.get("topic") or "General")
            stats[topic]["not_yet"] += 1

    weak_topics = []
    for topic, values in stats.items():
        total = values["total"]
        correct = values["correct"]
        accuracy = correct / total if total else 1.0
        wrong = total - correct
        if wrong or values["not_yet"]:
            weak_topics.append(
                {
                    "topic": topic,
                    "accuracy": round(accuracy, 2),
                    "correct": correct,
                    "total": total,
                    "not_yet": values["not_yet"],
                    "reason": _weak_topic_reason(correct, total, values["not_yet"]),
                }
            )

    return sorted(
        weak_topics,
        key=lambda item: (item["accuracy"], -item["not_yet"], -item["total"], item["topic"].lower()),
    )[:limit]


def _weak_topic_reason(correct: int, total: int, not_yet: int) -> str:
    if total and correct < total:
        return f"{total - correct} missed quiz question{'s' if total - correct != 1 else ''}"
    if not_yet:
        return f"{not_yet} flashcard{'s' if not_yet != 1 else ''} marked Not yet"
    return "Needs a little review"


def build_recommendations(
    sessions: list[dict],
    attempts_by_session: dict[int, list[dict]],
    weak_topics_by_session: dict[int, list[dict]],
    flashcards_by_session: dict[int, list[dict]] | None = None,
    now: datetime | None = None,
    limit: int = 5,
) -> list[dict]:
    now = now or datetime.now()
    recommendations = []
    flashcards_by_session = flashcards_by_session or {}

    for session in sessions:
        session_id = int(session["id"])
        title = session.get("title", "Lecture")
        weak_topics = weak_topics_by_session.get(session_id, [])
        attempts = attempts_by_session.get(session_id, [])
        cards = flashcards_by_session.get(session_id, [])

        if weak_topics:
            topic = weak_topics[0]["topic"]
            recommendations.append(
                {
                    "session_id": session_id,
                    "title": title,
                    "action": "practice_topic",
                    "topic": topic,
                    "reason": f"Let's strengthen {topic}.",
                    "priority": 0,
                }
            )
            continue

        if not attempts:
            recommendations.append(
                {
                    "session_id": session_id,
                    "title": title,
                    "action": "quiz",
                    "topic": "",
                    "reason": "You haven't tried the quiz yet.",
                    "priority": 1,
                }
            )
            continue

        if cards and all(str(card.get("status", "")).lower() != "got_it" for card in cards):
            recommendations.append(
                {
                    "session_id": session_id,
                    "title": title,
                    "action": "flashcards",
                    "topic": "",
                    "reason": "Your flashcards are ready for review.",
                    "priority": 2,
                }
            )
            continue

        days = _days_since(session.get("created_at"), now)
        if days >= 7:
            recommendations.append(
                {
                    "session_id": session_id,
                    "title": title,
                    "action": "summary",
                    "topic": "",
                    "reason": f"You haven't reviewed this in {days} days.",
                    "priority": 3,
                }
            )

    return sorted(recommendations, key=lambda item: (item["priority"], item["title"].lower()))[:limit]


def _days_since(value: str | None, now: datetime) -> int:
    if not value:
        return 0
    try:
        created = datetime.fromisoformat(value)
    except ValueError:
        return 0
    return max(0, (now - created).days)
