from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from resume_cli.build import BuildResult, PdfRenderError, PdfReport
from resume_cli.cli import (
    _build_tailored_until_one_page,
    _fit_candidate_ids,
    _normalize_batch_reviews,
    _review_bullet_from_session,
    _snapshot,
    _undo,
    _unique_slug,
    app,
)
from resume_cli.resume import append_bullet, parse_resume
from resume_cli.session import Session


REPO_ROOT = Path(__file__).resolve().parents[1]


class CliSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_help_lists_both_modes(self) -> None:
        result = self.runner.invoke(app, ["--help"])
        self.assertEqual(0, result.exit_code)
        self.assertIn("tailor", result.stdout)
        self.assertIn("review", result.stdout)
        self.assertIn("resume", result.stdout)

    def test_tailor_yes_cannot_bypass_line_review(self) -> None:
        result = self.runner.invoke(app, ["tailor", "--yes", "--job-text", "Example job"])
        self.assertNotEqual(0, result.exit_code)
        self.assertIn("cannot skip the required line-by-line review", result.output)

    def test_status_checks_real_repository(self) -> None:
        result = self.runner.invoke(app, ["status"])
        self.assertEqual(0, result.exit_code)
        self.assertIn("Root entries", result.stdout)
        self.assertIn("Tailored versions", result.stdout)

    def test_default_menu_can_show_status(self) -> None:
        result = self.runner.invoke(app, [], input="4\n")
        self.assertEqual(0, result.exit_code)
        self.assertIn("Resume CLI status", result.stdout)

    def test_review_finds_original_metadata_after_append_shifts_its_id(self) -> None:
        source = (REPO_ROOT / "_resume.tex").read_text(encoding="utf-8")
        document = parse_resume(source)
        bcg = next(entry for entry in document.entries if entry.title == "Boston Consulting Group (BCG)")
        technology = bcg.bullets[-1]
        session = Session.create(mode="review", target=".", job_description="")
        session.working_tex = append_bullet(source, bcg.id, "New verified bullet.")
        session.payload["bullet_records"] = {
            technology.id: {"entry_title": technology.entry_title, "text": technology.text}
        }
        resolved = _review_bullet_from_session(session, technology.id)
        self.assertEqual(technology.text, resolved.text)
        self.assertNotEqual(technology.id, resolved.id)

    def test_existing_slug_gets_a_safe_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "example-role").mkdir()
            with patch("resume_cli.cli.REPO_ROOT", root):
                self.assertEqual("example-role-2", _unique_slug("example-role"))

    def test_undo_restores_working_source_and_queued_root_appends(self) -> None:
        session = Session.create(mode="review", target="finance-consulting", job_description="")
        session.working_tex = "before"
        session.source_appends = [{"entry_title": "Shopee", "text": "existing"}]
        session.payload["bullet_records"] = {"bullet": {"entry_title": "Shopee", "text": "before"}}
        _snapshot(session)
        session.working_tex = "after"
        session.source_appends.append({"entry_title": "BCG", "text": "new"})
        session.payload["bullet_records"]["bullet"]["text"] = "after"
        self.assertTrue(_undo(session))
        self.assertEqual("before", session.working_tex)
        self.assertEqual([{"entry_title": "Shopee", "text": "existing"}], session.source_appends)
        self.assertEqual("before", session.payload["bullet_records"]["bullet"]["text"])

    def test_pdf_renderer_failure_does_not_trigger_resume_rewrite(self) -> None:
        session = Session.create(mode="tailor", target="example-role", job_description="job")
        session.working_tex = "resume source"
        report = PdfReport(
            path=REPO_ROOT / "example-role" / "Morgan_Le_Resume.pdf",
            pages=1,
            a4=True,
            extracted_characters=[100],
            links=1,
        )

        class ChatThatMustNotRun:
            def run_json(self, *args: object, **kwargs: object) -> object:
                raise AssertionError("QA infrastructure errors must not trigger Codex revisions")

        with (
            patch("resume_cli.cli.build_resume", return_value=BuildResult(report=report, output="")),
            patch("resume_cli.cli._visual_pdf_qa", side_effect=PdfRenderError("renderer unavailable")),
        ):
            with self.assertRaisesRegex(PdfRenderError, "renderer unavailable"):
                _build_tailored_until_one_page(
                    chat=ChatThatMustNotRun(),
                    session=session,
                    root_source="root source",
                    target="example-role",
                    confirm_revisions=False,
                )

    def test_batch_review_requires_every_line_in_source_order(self) -> None:
        records = [{"id": "one"}, {"id": "two"}]
        reviews = [{"line_id": "one"}, {"line_id": "two"}]
        self.assertEqual(
            {"one": reviews[0], "two": reviews[1]},
            _normalize_batch_reviews({"reviews": reviews}, records),
        )
        with self.assertRaisesRegex(Exception, "source order"):
            _normalize_batch_reviews({"reviews": list(reversed(reviews))}, records)

    def test_page_fit_prioritizes_metadata_then_low_relevance(self) -> None:
        session = Session.create(mode="tailor", target="", job_description="job")
        session.payload = {
            "line_ids": ["strong", "metadata", "weak"],
            "line_records": {
                "strong": {"is_metadata": False},
                "metadata": {"is_metadata": True},
                "weak": {"is_metadata": False},
            },
            "recommendations": {
                "strong": {"relevance_score": 9},
                "metadata": {"relevance_score": 8},
                "weak": {"relevance_score": 2},
            },
            "decisions": {},
            "fit_skipped": [],
        }
        self.assertEqual(["metadata", "weak", "strong"], _fit_candidate_ids(session))



if __name__ == "__main__":
    unittest.main()
