import unittest

import advanced_outputs


MIND_MAP = {
    "label": "AI Lecture",
    "note": "Main topic",
    "children": [
        {
            "label": "Grounding",
            "note": "Use source material",
            "children": [{"label": "Citations", "note": "Show where ideas came from"}],
        }
    ],
}


class AdvancedOutputsTests(unittest.TestCase):
    def test_validate_mind_map_and_outline(self) -> None:
        tree = advanced_outputs.validate_mind_map(MIND_MAP)
        self.assertEqual(tree["label"], "AI Lecture")
        outline = advanced_outputs.mind_map_to_outline(tree)
        self.assertIn("- AI Lecture: Main topic", outline)
        self.assertIn("  - Grounding: Use source material", outline)

    def test_mind_map_rejects_empty_root(self) -> None:
        with self.assertRaises(ValueError):
            advanced_outputs.validate_mind_map({"label": "", "children": []})

    def test_citation_mapping_uses_real_timestamps(self) -> None:
        transcript = "[0:10] Grounded outputs use the lecture transcript. [0:45] Flashcards help review."
        source = advanced_outputs.best_source_ref("lecture transcript grounding", transcript)
        self.assertIsNotNone(source)
        self.assertEqual(source["label"], "0:10")
        self.assertEqual(source["seconds"], 10)

    def test_export_sections_skip_missing_values(self) -> None:
        sections = advanced_outputs.export_sections(
            {
                "short_summary": "Short",
                "quiz": "",
                "transcript": "Full transcript",
                "mind_map": MIND_MAP,
            },
            {"include_transcript": False, "include_quiz": True, "include_mind_map": True},
        )
        headings = [heading for heading, _body in sections]
        self.assertIn("Short Summary", headings)
        self.assertIn("Mind Map Outline", headings)
        self.assertNotIn("Quiz", headings)
        self.assertNotIn("Full Transcript", headings)


if __name__ == "__main__":
    unittest.main()
