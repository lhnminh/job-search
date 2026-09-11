from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfWriter


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VALIDATION_SCRIPTS = REPOSITORY_ROOT / ".agents" / "skills" / "tailor-resume" / "scripts"
sys.path.insert(0, str(VALIDATION_SCRIPTS))

from resume_validation import (  # noqa: E402
    MASTER_SOURCE_RELATIVE_PATH,
    ResumeValidationError,
    _contact_fields,
    parse_resume,
    tailored_source_path,
    validate_tailored_completeness,
    validate_tailored_tex,
    verify_pdf,
)


class ResumeValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))
        from md_to_latex import parse_md_resume, render_loc

        cls.source = (REPOSITORY_ROOT / "public" / "resume.md").read_text(encoding="utf-8")
        cls.source += """

### Example Validation Project | Test Fixture
*2026*
- Built a deterministic fixture for resume-validation tests.
"""
        cls.latex_source = render_loc(parse_md_resume(cls.source))

    def test_parses_reference_entries(self) -> None:
        entries = parse_resume(self.source)
        self.assertGreaterEqual(len(entries), 2)
        self.assertGreaterEqual(sum(len(entry.bullets) for entry in entries), 2)

    def test_parses_jake_entries_and_bullets(self) -> None:
        source = r"""
\begin{document}
\section{Relevant Experience}
\resumeSubheading{Shopee}{Jun 2025 -- Jun 2026}{Analyst}{}
\resumeItem{Improved a verified process by 20\%.}
\resumeItem{\textbf{Technologies:} Python.}
\section{Projects}
\resumeProjectHeading{\textbf{Example} $|$ \emph{Tool}}{Aug 2026}
\resumeItem{Created a verified tool.}
\end{document}
"""
        entries = parse_resume(source)
        self.assertEqual(2, len(entries))
        self.assertEqual("Shopee", entries[0].title)
        self.assertEqual("Jun 2025 -- Jun 2026", entries[0].date)
        self.assertEqual(2, len(entries[0].bullets))
        self.assertTrue(entries[0].bullets[1].is_metadata)
        self.assertEqual("Example", entries[1].title)

    def test_parses_original_jake_inline_contact_header(self) -> None:
        source = r"""
\begin{document}
\begin{center}
  \textbf{\Huge \scshape Sample Applicant} \\ \vspace{1pt}
  \small 212-555-0100 $|$
  \href{mailto:email@example.com}{\underline{email@example.com}} $|$
  \href{https://www.linkedin.com/in/your-profile/}{\underline{linkedin.com/in/your-profile}} $|$
  \href{https://github.com/your-handle}{\underline{github.com/your-handle}}
\end{center}
\end{document}
"""
        self.assertEqual(
            {
                "firstname": ("Sample",),
                "familyname": ("Applicant",),
                "mobile": ("212-555-0100",),
                "email": ("email@example.com",),
                "linkedin": (
                    "https://www.linkedin.com/in/your-profile/",
                    "linkedin.com/in/your-profile",
                ),
                "github": ("https://github.com/your-handle", "github.com/your-handle"),
            },
            _contact_fields(source),
        )

    def test_rejects_changed_historical_title(self) -> None:
        changed = self.latex_source.replace(
            "{\\itshape Consultant}{Jan 2025",
            "{\\itshape Senior Consultant}{Jan 2025",
            1,
        )
        errors = validate_tailored_tex(self.source, changed)
        self.assertTrue(any("Historical title changed" in error for error in errors))

    def test_rejects_changed_mobile_number(self) -> None:
        changed = re.sub(
            r"\\mobile\{[^}]+\}",
            r"\\mobile{000-000-0000}",
            self.latex_source,
            count=1,
        )
        errors = validate_tailored_tex(self.source, changed)
        self.assertIn("Contact field changed or is missing: \\mobile", errors)

    def test_rejects_unverified_numeric_claim(self) -> None:
        changed = self.latex_source.replace("data-driven analyses", "\\$999M of data-driven analyses", 1)
        errors = validate_tailored_tex(self.source, changed)
        self.assertTrue(any("$999M" in error for error in errors))

    def test_requires_every_experience_entry(self) -> None:
        peloton_start = self.latex_source.index(
            "{\\customcventry{\\href{https://www.onepeloton.com/company}{Peloton}}"
        )
        samsung_start = self.latex_source.index(
            "{\\customcventry{\\href{https://www.samsung.com/us/about-us/our-business/}{Samsung Electronics America}}"
        )
        changed = self.latex_source[:peloton_start] + self.latex_source[samsung_start:]
        errors = validate_tailored_completeness(self.source, changed)
        self.assertIn("Missing experience entry: Peloton", errors)

    def test_allows_an_explicitly_excluded_project(self) -> None:
        first_project_start = self.latex_source.index(
            "{\\customcventry{\\href{https://github.com/lhnminh/zephyr-aq}{ZephyrAQ}}"
        )
        second_project_start = self.latex_source.index(
            "{\\customcventry{Example Validation Project}"
        )
        changed = self.latex_source[:first_project_start] + self.latex_source[second_project_start:]
        errors = validate_tailored_completeness(self.source, changed)
        self.assertEqual([], errors)

    def test_rejects_target_outside_repository(self) -> None:
        with self.assertRaises(ResumeValidationError):
            tailored_source_path(REPOSITORY_ROOT, "../../outside")

    def test_rejects_master_as_tailored_target(self) -> None:
        with self.assertRaises(ResumeValidationError):
            tailored_source_path(REPOSITORY_ROOT, "master")

    def test_premade_container_resolves_to_jake_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            jake = root / "pre-made" / "example" / "Jake"
            jake.mkdir(parents=True)
            expected = jake / "_resume.tex"
            expected.write_text("example", encoding="utf-8")
            self.assertEqual(expected.resolve(), tailored_source_path(root, "pre-made/example"))


    def test_rejects_non_compatibility_pdf_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resume.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=595.28, height=841.89)
            writer.write(path)
            with self.assertRaisesRegex(ResumeValidationError, "compatibility version 1.5"):
                verify_pdf(path)


if __name__ == "__main__":
    unittest.main()
