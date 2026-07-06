from datetime import datetime
import unittest

import study_intelligence


QUESTIONS = [
    {
        "id": "q1",
        "topic": "Photosynthesis steps",
        "question": "What comes first?",
        "options": {"A": "Light capture", "B": "Sleep", "C": "Digestion", "D": "Boiling"},
        "answer": "A",
        "explanation": "The lecture says light is captured first.",
    },
    {
        "id": "q2",
        "topic": "Light-dependent reactions",
        "question": "Where does this happen?",
        "options": {"A": "Roots", "B": "Thylakoids", "C": "Clouds", "D": "Stems"},
        "answer": "B",
        "explanation": "The lecture ties this to thylakoids.",
    },
]


class StudyIntelligenceTests(unittest.TestCase):
    def test_quiz_validation_rejects_missing_options(self) -> None:
        with self.assertRaises(ValueError):
            study_intelligence.validate_quiz_questions([{"question": "Bad", "options": {"A": "Only one"}, "answer": "A"}])

    def test_score_quiz_attempt(self) -> None:
        result = study_intelligence.score_quiz_attempt(QUESTIONS, {"q1": "A", "q2": "C"})
        self.assertEqual(result["score"], 1)
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["percent"], 50)
        self.assertFalse(result["results"][1]["is_correct"])

    def test_weak_topics_use_quiz_and_flashcards(self) -> None:
        attempt = study_intelligence.score_quiz_attempt(QUESTIONS, {"q1": "A", "q2": "C"})
        weak = study_intelligence.compute_weak_topics(
            [attempt],
            [{"topic": "Photosynthesis steps", "status": "not_yet"}],
        )
        topics = [item["topic"] for item in weak]
        self.assertIn("Light-dependent reactions", topics)
        self.assertIn("Photosynthesis steps", topics)

    def test_recommendations_prioritize_weak_topics(self) -> None:
        sessions = [
            {"id": 1, "title": "Lecture A", "created_at": "2026-06-01T10:00:00"},
            {"id": 2, "title": "Lecture B", "created_at": "2026-07-03T10:00:00"},
        ]
        recommendations = study_intelligence.build_recommendations(
            sessions,
            attempts_by_session={2: []},
            weak_topics_by_session={1: [{"topic": "Graph retrieval"}]},
            now=datetime(2026, 7, 4, 10, 0, 0),
        )
        self.assertEqual(recommendations[0]["action"], "practice_topic")
        self.assertEqual(recommendations[0]["topic"], "Graph retrieval")


if __name__ == "__main__":
    unittest.main()
