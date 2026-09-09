from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VALIDATION_SCRIPTS = REPOSITORY_ROOT / ".agents" / "skills" / "tailor-resume" / "scripts"
sys.path.insert(0, str(VALIDATION_SCRIPTS))

from resume_validation import (  # noqa: E402
    MASTER_SOURCE_RELATIVE_PATH,
    ResumeValidationError,
    parse_resume,
    tailored_source_path,
    validate_tailored_completeness,
    validate_tailored_tex,
)


class ResumeValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (REPOSITORY_ROOT / MASTER_SOURCE_RELATIVE_PATH).read_text(encoding="utf-8")

    def test_parses_reference_entries(self) -> None:
        entries = parse_resume(self.source)
        self.assertEqual(11, len(entries))
        self.assertEqual(31, sum(len(entry.bullets) for entry in entries))

    def test_rejects_changed_historical_title(self) -> None:
        changed = self.source.replace(
            "{\\itshape Consultant}{Jan 2025",
            "{\\itshape Senior Consultant}{Jan 2025",
            1,
        )
        errors = validate_tailored_tex(self.source, changed)
        self.assertTrue(any("Historical title changed" in error for error in errors))

    def test_rejects_old_mobile_number(self) -> None:
        changed = self.source.replace(
            "\\mobile{+1 347 774 6979}",
            "\\mobile{(+84)93 658-5869}",
            1,
        )
        errors = validate_tailored_tex(self.source, changed)
        self.assertIn("Contact field changed or is missing: \\mobile", errors)

    def test_rejects_unverified_numeric_claim(self) -> None:
        changed = self.source.replace("data-driven analyses", "\\$999M of data-driven analyses", 1)
        errors = validate_tailored_tex(self.source, changed)
        self.assertTrue(any("$999M" in error for error in errors))

    def test_requires_every_experience_entry(self) -> None:
        peloton_start = self.source.index(
            "{\\customcventry{\\href{https://www.onepeloton.com/company}{Peloton}}"
        )
        samsung_start = self.source.index(
            "{\\customcventry{\\href{https://www.samsung.com/us/about-us/our-business/}{Samsung Electronics America}}"
        )
        changed = self.source[:peloton_start] + self.source[samsung_start:]
        errors = validate_tailored_completeness(self.source, changed)
        self.assertIn("Missing experience entry: Peloton", errors)

    def test_allows_an_explicitly_excluded_project(self) -> None:
        housing_start = self.source.index(
            "{\\customcventry{\\href{https://github.com/lhnminh/Kaggle-Housing-Prices-Comp}{Housing Prices Competition}}"
        )
        axiom_start = self.source.index(
            "{\\customcventry{\\href{https://github.com/lhnminh/axiom}{Axiom}}"
        )
        changed = self.source[:housing_start] + self.source[axiom_start:]
        errors = validate_tailored_completeness(self.source, changed)
        self.assertEqual([], errors)

    def test_rejects_target_outside_repository(self) -> None:
        with self.assertRaises(ResumeValidationError):
            tailored_source_path(REPOSITORY_ROOT, "../../outside")

    def test_rejects_master_as_tailored_target(self) -> None:
        with self.assertRaises(ResumeValidationError):
            tailored_source_path(REPOSITORY_ROOT, "master")


if __name__ == "__main__":
    unittest.main()
