from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(REPOSITORY_ROOT / "webapp"))

from workspace import WorkspaceError, WorkspaceStore  # noqa: E402


class WorkspaceStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repository = Path(self.temporary_directory.name)
        (self.repository / "master").mkdir()
        shutil.copy(REPOSITORY_ROOT / "master" / "_resume.tex", self.repository / "master")
        self.store = WorkspaceStore(self.repository)
        self.session = self.store.create_session(
            company="Example Company",
            role="Data Scientist",
            job_description=(
                "Build production machine-learning models, create reliable data pipelines, "
                "communicate analysis to business partners, and use Python and SQL. "
                "Candidates should have experience evaluating models and working across teams."
            ),
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _analysis(self) -> tuple[list[dict], list[dict], list[dict]]:
        requirements = [
            {
                "id": "ml",
                "text": "Build and evaluate machine-learning models",
                "category": "required",
                "source_excerpt": "Build production machine-learning models",
            },
            {
                "id": "data",
                "text": "Create reliable data pipelines",
                "category": "responsibility",
                "source_excerpt": "create reliable data pipelines",
            },
            {
                "id": "eligibility",
                "text": "Prior model-evaluation experience",
                "category": "eligibility",
                "source_excerpt": "experience evaluating models",
            },
        ]
        bullet_suggestions = []
        project_suggestions = []
        for entry in self.session["entries"]:
            if entry["is_project"]:
                project_suggestions.append(
                    {
                        "entry_number": entry["entry_number"],
                        "action": "include",
                        "reason": "Shows relevant technical work.",
                        "requirement_id": "ml",
                    }
                )
            for bullet in entry["bullets"]:
                bullet_suggestions.append(
                    {
                        "entry_number": entry["entry_number"],
                        "bullet_number": bullet["bullet_number"],
                        "action": "keep",
                        "reason": "Provides verified supporting evidence.",
                        "requirement_id": "data",
                    }
                )
        return requirements, bullet_suggestions, project_suggestions

    def _save_analysis(self) -> dict:
        requirements, bullets, projects = self._analysis()
        return self.store.save_analysis(
            self.session["session_id"],
            requirements=requirements,
            bullet_suggestions=bullets,
            project_suggestions=projects,
        )

    def test_master_is_loaded_without_an_upload(self) -> None:
        master = self.store.master()
        self.assertEqual("ready", master["status"])
        self.assertGreater(master["entry_count"], 0)
        self.assertTrue(any(entry["title"] == "Columbia University" for entry in master["entries"]))

    def test_complete_analysis_is_required(self) -> None:
        requirements, bullets, projects = self._analysis()
        with self.assertRaisesRegex(WorkspaceError, "missing"):
            self.store.save_analysis(
                self.session["session_id"],
                requirements=requirements,
                bullet_suggestions=bullets[:-1],
                project_suggestions=projects,
            )

    def test_analysis_exposes_every_suggestion_at_once(self) -> None:
        session = self._save_analysis()
        expected_bullets = sum(len(entry["bullets"]) for entry in session["entries"])
        expected_projects = sum(entry["is_project"] for entry in session["entries"])
        self.assertEqual(expected_bullets, len(session["suggestions"]["bullets"]))
        self.assertEqual(expected_projects, len(session["suggestions"]["projects"]))
        self.assertGreater(session["decision_counts"]["unresolved"], 0)
        unsupported = next(item for item in session["requirements"] if item["id"] == "eligibility")
        self.assertFalse(unsupported["supported"])
        self.assertTrue(unsupported["eligibility_mismatch"])
        self.assertEqual("experience evaluating models", unsupported["source_excerpt"])

    def test_session_stage_and_next_unresolved_are_derived_from_saved_state(self) -> None:
        self.assertEqual("Preparing suggestions", self.session["stage"])
        session = self._save_analysis()
        self.assertEqual("Reviewing suggestions", session["stage"])
        self.assertEqual("bullet", session["next_unresolved"]["kind"])

        decisions = []
        projects = []
        for entry in session["entries"]:
            if entry["is_project"]:
                projects.append({"entry_number": entry["entry_number"], "action": "exclude"})
                continue
            decisions.extend(
                {
                    "entry_number": entry["entry_number"],
                    "bullet_number": bullet["bullet_number"],
                    "action": "keep",
                }
                for bullet in entry["bullets"]
            )
        resolved = self.store.apply_decisions(
            session["session_id"], bullet_decisions=decisions, project_decisions=projects
        )
        self.assertEqual("Page fit", resolved["stage"])
        self.assertIsNone(resolved["next_unresolved"])

    def test_requirement_excerpt_must_come_from_the_job_description(self) -> None:
        requirements, bullets, projects = self._analysis()
        requirements[0]["source_excerpt"] = "This wording is not in the supplied role"
        with self.assertRaisesRegex(WorkspaceError, "not in the job description"):
            self.store.save_analysis(
                self.session["session_id"],
                requirements=requirements,
                bullet_suggestions=bullets,
                project_suggestions=projects,
            )

    def test_decisions_are_atomic_and_undoable(self) -> None:
        session = self._save_analysis()
        first_entry = session["entries"][0]
        project = next(entry for entry in session["entries"] if entry["is_project"])
        updated = self.store.apply_decisions(
            session["session_id"],
            bullet_decisions=[
                {"entry_number": first_entry["entry_number"], "bullet_number": 1, "action": "keep"}
            ],
            project_decisions=[{"entry_number": project["entry_number"], "action": "include"}],
        )
        self.assertEqual("keep", updated["entries"][0]["bullets"][0]["decision"]["action"])
        restored = self.store.undo(session["session_id"])
        self.assertIsNone(restored["entries"][0]["bullets"][0]["decision"])
        restored_project = next(entry for entry in restored["entries"] if entry["is_project"])
        self.assertIsNone(restored_project["project_decision"])

    def test_other_can_request_and_receive_a_revised_suggestion(self) -> None:
        session = self._save_analysis()
        first = session["entries"][0]
        requested = self.store.request_revision(
            session["session_id"],
            entry_number=first["entry_number"],
            bullet_number=1,
            instruction="Emphasize the machine-learning result without adding a new metric.",
        )
        request = requested["revision_requests"][0]
        self.assertEqual("pending", request["status"])
        context = self.store.suggestion_context(session["session_id"])
        self.assertEqual(request["id"], context["revision_requests"][0]["id"])

        revised = self.store.save_revision(
            session["session_id"],
            request_id=request["id"],
            suggestion={
                "action": "rewrite",
                "suggested_text": "Grounded replacement wording",
                "reason": "Matches the requested emphasis using only verified experience.",
                "requirement_id": "ml",
            },
        )
        self.assertEqual("fulfilled", revised["revision_requests"][0]["status"])
        replacement = next(
            item
            for item in revised["suggestions"]["bullets"]
            if item["entry_number"] == first["entry_number"] and item["bullet_number"] == 1
        )
        self.assertEqual("Grounded replacement wording", replacement["suggested_text"])
        restored = self.store.undo(session["session_id"])
        original = next(
            item
            for item in restored["suggestions"]["bullets"]
            if item["entry_number"] == first["entry_number"] and item["bullet_number"] == 1
        )
        self.assertEqual("keep", original["action"])
        self.assertIsNone(original["suggested_text"])
        self.assertEqual([], restored["revision_requests"])

    def test_revision_request_is_undoable(self) -> None:
        session = self._save_analysis()
        first = session["entries"][0]
        requested = self.store.request_revision(
            session["session_id"],
            entry_number=first["entry_number"],
            bullet_number=1,
            instruction="Try a more concise version.",
        )
        self.assertEqual(1, len(requested["revision_requests"]))
        restored = self.store.undo(session["session_id"])
        self.assertEqual([], restored["revision_requests"])

    def test_assembly_applies_only_explicit_decisions(self) -> None:
        session = self._save_analysis()
        bullet_decisions = []
        project_decisions = []
        for entry in session["entries"]:
            if entry["is_project"]:
                project_decisions.append({"entry_number": entry["entry_number"], "action": "include"})
            for bullet in entry["bullets"]:
                bullet_decisions.append(
                    {
                        "entry_number": entry["entry_number"],
                        "bullet_number": bullet["bullet_number"],
                        "action": "keep",
                    }
                )
        self.store.apply_decisions(
            session["session_id"],
            bullet_decisions=bullet_decisions,
            project_decisions=project_decisions,
        )
        source = self.store.assemble_source(session["session_id"], require_complete=True)
        self.assertNotIn("\\newpage", source)
        self.assertIn("Vietnam National University", source)
        self.assertIn("Housing Prices Competition", source)

    def test_incomplete_session_cannot_export_source(self) -> None:
        session = self._save_analysis()
        with self.assertRaisesRegex(WorkspaceError, "before export"):
            self.store.assemble_source(session["session_id"], require_complete=True)

    def test_master_change_marks_session_stale(self) -> None:
        master = self.repository / "master" / "_resume.tex"
        master.write_text(master.read_text(encoding="utf-8") + "\n% changed\n", encoding="utf-8")
        session = self.store.get_session(self.session["session_id"])
        self.assertEqual("stale", session["status"])
        with self.assertRaisesRegex(WorkspaceError, "changed"):
            self._save_analysis()

    def test_reconcile_restarts_from_the_changed_master(self) -> None:
        session = self._save_analysis()
        master = self.repository / "master" / "_resume.tex"
        master.write_text(master.read_text(encoding="utf-8") + "\n% verified update\n", encoding="utf-8")
        reconciled = self.store.reconcile_session(session["session_id"])
        self.assertEqual("ready", reconciled["status"])
        self.assertIsNone(reconciled["suggestions"])
        self.assertEqual([], reconciled["history"])

    def test_archive_removes_session_from_active_list(self) -> None:
        session_id = self.session["session_id"]
        archived = self.store.archive_session(session_id)
        self.assertEqual("archived", archived["status"])
        self.assertEqual([], self.store.list_sessions())
        self.assertTrue((self.store.archive_directory / f"{session_id}.json").is_file())

    def test_new_decision_invalidates_an_old_preview(self) -> None:
        session = self._save_analysis()
        path, payload = self.store._load(session["session_id"])
        payload["preview"] = {"report": {"pages": 1}, "source_sha256": "old"}
        from workspace import _atomic_json

        _atomic_json(path, payload)
        first = session["entries"][0]
        updated = self.store.apply_decisions(
            session["session_id"],
            bullet_decisions=[
                {"entry_number": first["entry_number"], "bullet_number": 1, "action": "keep"}
            ],
        )
        self.assertIsNone(updated["preview"])

    def test_export_requires_a_current_one_page_preview(self) -> None:
        session = self._save_analysis()
        decisions = []
        projects = []
        for entry in session["entries"]:
            if entry["is_project"]:
                projects.append({"entry_number": entry["entry_number"], "action": "exclude"})
                continue
            for bullet in entry["bullets"]:
                decisions.append(
                    {"entry_number": entry["entry_number"], "bullet_number": bullet["bullet_number"], "action": "keep"}
                )
        self.store.apply_decisions(
            session["session_id"], bullet_decisions=decisions, project_decisions=projects
        )
        with self.assertRaisesRegex(WorkspaceError, "one-page preview"):
            self.store.export(session["session_id"])

    def test_failed_final_build_does_not_modify_an_existing_target(self) -> None:
        session = self._save_analysis()
        decisions = [
            {
                "entry_number": entry["entry_number"],
                "bullet_number": bullet["bullet_number"],
                "action": "keep",
            }
            for entry in session["entries"]
            if not entry["is_project"]
            for bullet in entry["bullets"]
        ]
        projects = [
            {"entry_number": entry["entry_number"], "action": "exclude"}
            for entry in session["entries"]
            if entry["is_project"]
        ]
        self.store.apply_decisions(
            session["session_id"], bullet_decisions=decisions, project_decisions=projects
        )
        source = self.store.assemble_source(session["session_id"], require_complete=True)
        from workspace import _atomic_json

        path, payload = self.store._load(session["session_id"])
        payload["preview"] = {
            "report": {"pages": 1},
            "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        }
        _atomic_json(path, payload)
        target = self.repository / session["target_slug"]
        target.mkdir()
        old_source = "existing source"
        old_pdf = b"existing pdf"
        (target / "_resume.tex").write_text(old_source, encoding="utf-8")
        (target / "Morgan_Le_Resume.pdf").write_bytes(old_pdf)

        def fail_build(_: str) -> dict:
            raise WorkspaceError("simulated final build failure")

        self.store._build_at = fail_build  # type: ignore[method-assign]
        with self.assertRaisesRegex(WorkspaceError, "simulated final build failure"):
            self.store.export(session["session_id"], overwrite=True)
        self.assertEqual(old_source, (target / "_resume.tex").read_text(encoding="utf-8"))
        self.assertEqual(old_pdf, (target / "Morgan_Le_Resume.pdf").read_bytes())

    def test_excluding_all_projects_removes_the_orphaned_heading(self) -> None:
        session = self._save_analysis()
        decisions = [
            {"entry_number": entry["entry_number"], "bullet_number": bullet["bullet_number"], "action": "keep"}
            for entry in session["entries"]
            if not entry["is_project"]
            for bullet in entry["bullets"]
        ]
        projects = [
            {"entry_number": entry["entry_number"], "action": "exclude"}
            for entry in session["entries"]
            if entry["is_project"]
        ]
        self.store.apply_decisions(
            session["session_id"], bullet_decisions=decisions, project_decisions=projects
        )
        source = self.store.assemble_source(session["session_id"], require_complete=True)
        self.assertNotIn("\\section{Projects}", source)

    @unittest.skipUnless(
        os.environ.get("RESUME_APP_PDF_INTEGRATION") == "1",
        "set RESUME_APP_PDF_INTEGRATION=1 to run the real Tectonic export",
    )
    def test_real_preview_and_export_are_one_page_a4(self) -> None:
        (self.repository / "scripts").mkdir()
        shutil.copy2(
            REPOSITORY_ROOT / "scripts" / "build_resume.sh",
            self.repository / "scripts" / "build_resume.sh",
        )
        shutil.copytree(REPOSITORY_ROOT / "shared", self.repository / "shared")
        session = self._save_analysis()
        decisions = [
            {
                "entry_number": entry["entry_number"],
                "bullet_number": bullet["bullet_number"],
                "action": "keep",
            }
            for entry in session["entries"]
            if not entry["is_project"]
            for bullet in entry["bullets"]
        ]
        projects = [
            {"entry_number": entry["entry_number"], "action": "exclude"}
            for entry in session["entries"]
            if entry["is_project"]
        ]
        self.store.apply_decisions(
            session["session_id"], bullet_decisions=decisions, project_decisions=projects
        )
        preview = self.store.build_preview(session["session_id"])
        self.assertEqual(1, preview["report"]["pages"])
        self.assertTrue(preview["report"]["a4"])
        self.assertGreater(preview["report"]["links"], 0)
        self.assertTrue(all(count > 0 for count in preview["report"]["extracted_characters"]))

        exported = self.store.export(session["session_id"])
        self.assertEqual(1, exported["report"]["pages"])
        target = self.repository / session["target_slug"]
        self.assertEqual(
            {"_resume.tex", "Morgan_Le_Resume.pdf"},
            {item.name for item in target.iterdir()},
        )


if __name__ == "__main__":
    unittest.main()
