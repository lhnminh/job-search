from __future__ import annotations

import unittest
from pathlib import Path

from scripts.diff_resume import resolve_resume_path, structured_diff, unified_text_diff
from scripts.md_to_latex import parse_md_resume


class DiffResumeTests(unittest.TestCase):
    def test_resolve_resume_path(self) -> None:
        p = resolve_resume_path("public")
        self.assertTrue(p.name == "resume.md")
        self.assertTrue(p.exists())

    def test_structured_diff(self) -> None:
        p1 = Path("public/resume.md").read_text(encoding="utf-8")
        p2 = p1.replace("Relevant Experience", "Selected Experience", 1)
        r1 = parse_md_resume(p1)
        r2 = parse_md_resume(p2)
        diff_str = structured_diff(r1, r2, use_color=False)
        self.assertIn("Summary:", diff_str)
        self.assertIn("Selected Experience", diff_str)

    def test_unified_text_diff(self) -> None:
        text1 = "# Morgan Le\n- Line 1\n"
        text2 = "# Morgan Le\n- Line 2\n"
        diff = unified_text_diff(text1, text2, "base", "target", use_color=False)
        self.assertIn("--- base", diff)
        self.assertIn("-- Line 1", diff)
        self.assertIn("+- Line 2", diff)


if __name__ == "__main__":
    unittest.main()
