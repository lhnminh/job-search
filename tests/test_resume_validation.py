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
    numeric_claims,
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

    def test_generated_jake_header_without_linkedin_preserves_contacts(self) -> None:
        from md_to_latex import parse_md_resume, render_jake
        source = "# Sample Applicant\n\n[email@example.com](mailto:email@example.com) | 212-555-0100\n"
        self.assertEqual(_contact_fields(source), _contact_fields(render_jake(parse_md_resume(source))))

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

    def test_commented_entries_and_bullets_are_not_verified(self) -> None:
        from md_to_latex import parse_md_resume, render_jake
        active = """# Sample Applicant
email@example.com | 212-555-0100
## Experience
### Active Company | Analyst
*2024 – Present*
- Built verified reporting tools.
"""
        hidden = """<!--
- Claimed $999M in savings and 99% growth.
### Fictional Company | Director
*2020 – 2023*
- Unverified example claim.
-->
"""
        root = "<!-- # Fictional Applicant\nfake@example.com | 000-000-0000 -->\n" + active + hidden
        entries = parse_resume(root)
        self.assertEqual(["Active Company"], [entry.title for entry in entries])
        self.assertEqual(1, len(entries[0].bullets))
        self.assertEqual(_contact_fields(active), _contact_fields(root))
        proposed = render_jake(parse_md_resume(active))
        self.assertEqual([], validate_tailored_tex(root, proposed))
        self.assertEqual([], validate_tailored_completeness(root, proposed))
        activated = proposed.replace("Built verified reporting tools.", "Claimed \\$999M in savings.")
        self.assertTrue(any("$999M" in error for error in validate_tailored_tex(root, activated)))
        fictional = active + hidden.replace("<!--", "").replace("-->", "")
        errors = validate_tailored_tex(root, render_jake(parse_md_resume(fictional)))
        self.assertIn("Unverified experience entry: Fictional Company", errors)

    def test_numeric_claims_ignore_comments_without_losing_active_percentages(self) -> None:
        self.assertEqual({"20%", "$100K"}, numeric_claims(
            "Grew by 20% and earned $100K. <!-- Claimed 99% and $999M. -->"))
        self.assertEqual({"20%"}, numeric_claims(
            r"\begin{document}" + "\nVerified 20\\%. % Hidden $999M\n" + r"\end{document}"))
        self.assertEqual(set(), numeric_claims("<!-- Unfinished example: $999M"))

    def test_unfinished_master_comment_does_not_hide_confirmed_facts(self) -> None:
        from md_to_latex import parse_md_resume, render_jake
        active = """# Sample Applicant
email@example.com | 212-555-0100
## Experience
### Active Company | Analyst
*2024 – Present*
- Built verified reporting tools.
"""
        root = active + "\n<!-- Unfinished example: $999M"
        proposed = render_jake(parse_md_resume(active.replace(
            "Built verified reporting tools.", "Earned $100K through verified reporting tools.")))
        self.assertEqual([], validate_tailored_tex(root, proposed, ["Earned $100K"]))

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

    def test_allows_one_substantive_bullet_for_every_experience_entry(self) -> None:
        root_source = """\
# Sample Applicant

## Relevant Experience

### Example Company | Analyst
*Jan 2025 – Present*
- Built a verified reporting workflow.
- Improved a verified operating process.
- **Technologies:** Python, SQL.
"""
        proposed_source = """\
# Sample Applicant

## Relevant Experience

### Example Company | Analyst
*Jan 2025 – Present*
- Built a verified reporting workflow.
- **Technologies:** Python, SQL.
"""
        errors = validate_tailored_completeness(root_source, proposed_source)
        self.assertEqual([], errors)
        metadata_only = proposed_source.replace("- Built a verified reporting workflow.\n", "")
        self.assertIn(
            "Too few substantive bullets for Example Company: expected at least 1, got 0",
            validate_tailored_completeness(root_source, metadata_only),
        )
        from md_to_latex import parse_md_resume, render_jake
        empty_bullet = render_jake(parse_md_resume(proposed_source)).replace(
            r"\resumeItem{Built a verified reporting workflow.}", r"\resumeItem{}"
        )
        self.assertIn(
            "Too few substantive bullets for Example Company: expected at least 1, got 0",
            validate_tailored_completeness(root_source, empty_bullet),
        )

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
