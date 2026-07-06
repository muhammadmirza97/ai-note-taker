import tempfile
import unittest
from pathlib import Path

import exporter
import file_store


def sample_session() -> dict:
    return {
        "id": 42,
        "title": "Intro to AI",
        "created_at": "2026-07-03T09:30:00",
        "source_type": "uploaded audio",
        "duration_seconds": 125,
        "short_summary": "AI systems can support learning.",
        "detailed_summary": "## Main Ideas\n\nThe lecture covered grounded study notes.",
        "key_points": "- Ground outputs in source material.",
        "terms": "- Transcript: text captured from spoken audio.",
        "quiz": "1. What should outputs use?\n   A. Source material\n   Answer: A - It was stated in the lecture.",
        "flashcards": [{"front": "What should outputs use?", "back": "Source material.", "topic": "Grounding"}],
        "summary": "Legacy summary fallback.",
        "transcript": "This is the full lecture transcript.",
    }


class ExportTests(unittest.TestCase):
    def test_combined_markdown_has_notebooklm_headings(self) -> None:
        session = sample_session()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            original_dirs = (
                file_store.OUTPUTS_DIR,
                file_store.TRANSCRIPTS_DIR,
                file_store.SUMMARIES_DIR,
                file_store.PDFS_DIR,
                file_store.COMBINED_DIR,
            )
            try:
                file_store.OUTPUTS_DIR = tmp_path
                file_store.TRANSCRIPTS_DIR = tmp_path / "transcripts"
                file_store.SUMMARIES_DIR = tmp_path / "summaries"
                file_store.PDFS_DIR = tmp_path / "pdfs"
                file_store.COMBINED_DIR = tmp_path / "combined"
                markdown_path = Path(file_store.write_combined(session))
                markdown = markdown_path.read_text(encoding="utf-8")
            finally:
                (
                    file_store.OUTPUTS_DIR,
                    file_store.TRANSCRIPTS_DIR,
                    file_store.SUMMARIES_DIR,
                    file_store.PDFS_DIR,
                    file_store.COMBINED_DIR,
                ) = original_dirs

        self.assertIn("# Intro to AI", markdown)
        self.assertIn("## Lecture Details", markdown)
        self.assertIn("## Short Summary", markdown)
        self.assertIn("## Detailed Notes", markdown)
        self.assertIn("## Key Points", markdown)
        self.assertIn("## Important Terms and Definitions", markdown)
        self.assertIn("## Quiz", markdown)
        self.assertIn("## Flashcards", markdown)
        self.assertIn("Front: What should outputs use?", markdown)
        self.assertIn("## Full Transcript", markdown)

    def test_pdf_export_returns_pdf_bytes(self) -> None:
        pdf = exporter.generate_pdf(sample_session())
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 1000)


if __name__ == "__main__":
    unittest.main()
