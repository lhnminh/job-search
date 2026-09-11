from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

from md_to_cover_letter import (  # noqa: E402
    parse_md_cover_letter,
    render_latex_cover_letter,
    find_placeholders,
    CoverLetter,
)
from diff_cover_letter import diff_cover_letters  # noqa: E402


SAMPLE_DOMINO_MD = """# Sample Applicant

[email@example.com](mailto:email@example.com) | 212-555-0100 | [portfolio.example](https://example.com/) | [linkedin.com/in/your-profile](https://www.linkedin.com/in/your-profile/)

September 10, 2026

Domino Data Lab
San Francisco, CA

Dear Domino Hiring Team,

I am excited to apply for the Forward Deployed Engineer Intern position at Domino. My background spans consulting, operations, and analytics.

My roles have required me to move between users, business problems, and technical execution. On one representative project, I supported a $10 billion initiative and built Python & SQL pipelines for P&L reporting, reducing processing time by 20%.

What appeals to me most about Domino is the opportunity to combine customer collaboration with hands-on engineering.

Sincerely,  
Sample Applicant
"""

SAMPLE_PREMADE_MD = """# Morgan Le

email@example.com | 212-555-0100
123 Example Street, Apt. 4E
New York, NY 10001

Date: ____________________

[Company Name]  
[Company Address]

Dear Hiring Manager,

I am excited to apply for the [Position Title] role at [Company Name].

Sincerely,  
Sample Applicant
"""


class MdToCoverLetterTests(unittest.TestCase):
    def test_parse_md_cover_letter(self) -> None:
        cl = parse_md_cover_letter(SAMPLE_DOMINO_MD)
        self.assertEqual("Sample Applicant", cl.name)
        self.assertEqual("Sample Applicant", cl.signature)
        self.assertIn("Domino Data Lab", cl.recipient_lines)
        self.assertIn("San Francisco, CA", cl.recipient_lines)
        self.assertEqual("Dear Domino Hiring Team,", cl.opening)
        self.assertEqual(3, len(cl.paragraphs))
        self.assertEqual("Sincerely,", cl.closing)
        self.assertTrue(any("212-555-0100" in item for item in cl.contact_items))
        self.assertTrue(any("email@example.com" in item for item in cl.contact_items))

    def test_render_latex_cover_letter(self) -> None:
        cl = parse_md_cover_letter(SAMPLE_DOMINO_MD)
        latex = render_latex_cover_letter(cl)
        self.assertIn(r"\date{September 10, 2026}", latex)
        self.assertIn(r"\opening{Dear Domino Hiring Team,}", latex)
        self.assertIn(r"\closing{Sincerely,}", latex)
        self.assertIn(r"\signature{Sample Applicant}", latex)
        self.assertIn(r"\vspace*{1.2in}", latex)
        self.assertIn(r"\topmargin=-1.251in", latex)
        self.assertIn(r"\def\@texttop{}", latex)
        self.assertIn(r"\textheight=9.6in", latex)
        # Check special character escaping
        self.assertIn(r"\$10 billion", latex)
        self.assertIn(r"Python \& SQL", latex)
        self.assertIn(r"P\&L", latex)
        self.assertIn(r"20\%", latex)

        premade_latex = render_latex_cover_letter(parse_md_cover_letter(SAMPLE_PREMADE_MD))
        self.assertIn(r"\date{\_", premade_latex)
        self.assertIn("\\\\{}\n[Company Address]", premade_latex)

    def test_find_placeholders(self) -> None:
        placeholders = find_placeholders(SAMPLE_PREMADE_MD)
        self.assertIn("[Company Name]", placeholders)
        self.assertIn("[Company Address]", placeholders)
        self.assertIn("[Position Title]", placeholders)
        self.assertTrue(any("___" in p for p in placeholders))

        # Domino sample should have zero unfilled placeholders
        domino_placeholders = find_placeholders(SAMPLE_DOMINO_MD)
        self.assertEqual(0, len(domino_placeholders))

    def test_diff_cover_letters(self) -> None:
        diff_str = diff_cover_letters(SAMPLE_PREMADE_MD, SAMPLE_DOMINO_MD, use_color=False)
        self.assertIn("+September 10, 2026", diff_str)
        self.assertIn("-Date: ____________________", diff_str)
        self.assertIn("+Domino Data Lab", diff_str)


if __name__ == "__main__":
    unittest.main()
