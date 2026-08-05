from __future__ import annotations

import unittest
from pathlib import Path

from resume_cli.resume import (
    append_bullet,
    append_bullet_by_title,
    parse_resume,
    remove_bullet,
    resume_path,
    replace_bullet,
    slugify,
    validate_root_append_only,
    validate_tailored_tex,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class ResumeParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (REPO_ROOT / "_resume.tex").read_text(encoding="utf-8")
        cls.document = parse_resume(cls.source)

    def test_parses_expected_entries_and_bullets(self) -> None:
        self.assertEqual(9, len(self.document.entries))
        self.assertEqual(25, sum(len(entry.bullets) for entry in self.document.entries))
        bcg = next(entry for entry in self.document.entries if entry.title == "Boston Consulting Group (BCG)")
        self.assertEqual("Consultant", bcg.subtitle)
        self.assertEqual(3, len(bcg.bullets))

    def test_replace_bullet_changes_only_selected_body(self) -> None:
        bcg = next(entry for entry in self.document.entries if entry.title == "Boston Consulting Group (BCG)")
        changed = replace_bullet(self.source, bcg.bullets[0].id, "Rewritten verified bullet.")
        updated = parse_resume(changed).entry(bcg.id)
        self.assertEqual("Rewritten verified bullet.", updated.bullets[0].text)
        self.assertEqual(bcg.bullets[1].text, updated.bullets[1].text)

    def test_remove_bullet_preserves_other_entries(self) -> None:
        bcg = next(entry for entry in self.document.entries if entry.title == "Boston Consulting Group (BCG)")
        changed = remove_bullet(self.source, bcg.bullets[1].id)
        updated = parse_resume(changed).entry(bcg.id)
        self.assertEqual(2, len(updated.bullets))
        self.assertIn("Partnered with", updated.bullets[0].text)

    def test_append_is_additive_and_idempotent(self) -> None:
        bcg = next(entry for entry in self.document.entries if entry.title == "Boston Consulting Group (BCG)")
        new_text = "Appended a verified consulting bullet."
        changed = append_bullet(self.source, bcg.id, new_text)
        changed_twice = append_bullet(changed, bcg.id, new_text)
        updated = parse_resume(changed_twice).entry(bcg.id)
        self.assertEqual(4, len(updated.bullets))
        self.assertEqual(new_text, updated.bullets[-2].text)
        self.assertTrue(updated.bullets[-1].is_metadata)
        self.assertEqual([], validate_root_append_only(self.source, changed_twice))

    def test_append_by_title_targets_matching_entry(self) -> None:
        changed = append_bullet_by_title(self.source, "Shopee", "Appended verified Shopee bullet.")
        shopee = next(entry for entry in parse_resume(changed).entries if entry.title == "Shopee")
        self.assertEqual("Appended verified Shopee bullet.", shopee.bullets[-2].text)

    def test_append_validator_rejects_replacement(self) -> None:
        changed = self.source.replace("Product Operations and Analytics Associate", "Product Manager", 1)
        self.assertTrue(validate_root_append_only(self.source, changed))

    def test_tailored_validator_rejects_historical_title_change(self) -> None:
        changed = self.source.replace("{\\itshape Consultant}{Jan 2025", "{\\itshape Senior Consultant}{Jan 2025", 1)
        errors = validate_tailored_tex(self.source, changed)
        self.assertTrue(any("Historical title changed" in error for error in errors))

    def test_tailored_validator_rejects_historical_date_change(self) -> None:
        changed = self.source.replace("{Jan 2025 - Jun 2025}", "{Jan 2024 - Jun 2025}", 1)
        errors = validate_tailored_tex(self.source, changed)
        self.assertTrue(any("Historical dates changed" in error for error in errors))

    def test_tailored_validator_rejects_contact_change(self) -> None:
        changed = self.source.replace("morgan.hn.le@gmail.com", "different@example.com", 1)
        errors = validate_tailored_tex(self.source, changed)
        self.assertTrue(any("email" in error for error in errors))

    def test_tailored_validator_rejects_new_numeric_claim(self) -> None:
        changed = self.source.replace("data-driven analyses", "\\$999M of data-driven analyses", 1)
        errors = validate_tailored_tex(self.source, changed)
        self.assertTrue(any("$999M" in error for error in errors))

    def test_confirmed_fact_allows_new_numeric_claim(self) -> None:
        changed = self.source.replace("data-driven analyses", "\\$999M of data-driven analyses", 1)
        errors = validate_tailored_tex(self.source, changed, ["The project involved $999M."])
        self.assertFalse(any("$999M" in error for error in errors))

    def test_slugify(self) -> None:
        self.assertEqual("macquarie-real-estate-intern", slugify("Macquarie — Real Estate Intern"))

    def test_resume_path_rejects_repository_escape(self) -> None:
        with self.assertRaises(ValueError):
            resume_path(REPO_ROOT, "../../outside")


if __name__ == "__main__":
    unittest.main()
