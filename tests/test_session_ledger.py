from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = REPOSITORY_ROOT / ".agents" / "skills" / "tailor-resume" / "scripts"
sys.path.insert(0, str(SKILL_SCRIPTS))

from resume_validation import MASTER_SOURCE_RELATIVE_PATH  # noqa: E402
from session_ledger import (  # noqa: E402
    SessionLedgerError,
    apply_decision_batch,
    create_session,
    ledger_path,
    list_sessions,
    project_selection_snapshot,
    session_snapshot,
    undo_last_batch,
)


class SessionLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repository = Path(self.temporary_directory.name)
        master = self.repository / MASTER_SOURCE_RELATIVE_PATH
        master.parent.mkdir(parents=True)
        source = (REPOSITORY_ROOT / MASTER_SOURCE_RELATIVE_PATH).read_text(encoding="utf-8")
        master.write_text(source, encoding="utf-8")
        create_session(
            self.repository,
            "example-role",
            "example-role",
            "Analyze operations and build financial models.",
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_fast_resume_returns_only_active_entry(self) -> None:
        snapshot = session_snapshot(self.repository, "example-role")
        self.assertEqual("ready", snapshot["status"])
        self.assertEqual(1, snapshot["current_entry"]["entry_number"])
        self.assertNotIn("job_description", snapshot)
        self.assertNotIn("entries", snapshot)
        self.assertNotIn("source_latex", snapshot["current_entry"]["bullets"][0])

    def test_fast_resume_detects_changed_master(self) -> None:
        master = self.repository / MASTER_SOURCE_RELATIVE_PATH
        master.write_text(master.read_text(encoding="utf-8") + "\n% changed\n", encoding="utf-8")
        snapshot = session_snapshot(self.repository, "example-role")
        self.assertEqual("stale", snapshot["status"])
        self.assertNotIn("current_entry", snapshot)

        with self.assertRaises(SessionLedgerError):
            apply_decision_batch(
                self.repository,
                "example-role",
                [{"entry_number": 1, "bullet_number": 1, "action": "keep"}],
            )

    def test_project_shortlist_returns_all_projects_without_bullet_text(self) -> None:
        snapshot = project_selection_snapshot(self.repository, "example-role")
        self.assertEqual("ready", snapshot["status"])
        self.assertGreaterEqual(len(snapshot["projects"]), 2)
        self.assertTrue(all(project["project_decision"] is None for project in snapshot["projects"]))
        self.assertTrue(all("bullets" not in project for project in snapshot["projects"]))
        self.assertTrue(all(project["bullet_count"] >= 1 for project in snapshot["projects"]))

    def test_project_choices_are_saved_separately_from_bullet_decisions(self) -> None:
        projects = project_selection_snapshot(self.repository, "example-role")["projects"]
        included_entry = projects[0]["entry_number"]
        excluded_entry = projects[1]["entry_number"]

        snapshot = apply_decision_batch(
            self.repository,
            "example-role",
            [],
            project_decisions=[
                {"entry_number": included_entry, "action": "include"},
                {"entry_number": excluded_entry, "action": "exclude"},
            ],
            current_entry_number=included_entry,
        )

        self.assertEqual("include", snapshot["current_entry"]["project_decision"]["action"])
        self.assertTrue(
            all(bullet["decision"] is None for bullet in snapshot["current_entry"]["bullets"])
        )
        choices = project_selection_snapshot(self.repository, "example-role")["projects"]
        self.assertEqual("exclude", choices[1]["project_decision"]["action"])

    def test_project_choice_rejects_non_project_entries(self) -> None:
        with self.assertRaisesRegex(SessionLedgerError, "is not a project"):
            apply_decision_batch(
                self.repository,
                "example-role",
                [],
                project_decisions=[{"entry_number": 1, "action": "exclude"}],
            )

    def test_batch_saves_multiple_decisions_with_one_atomic_replace(self) -> None:
        decisions = [
            {"entry_number": 1, "bullet_number": 1, "action": "keep"},
            {
                "entry_number": 2,
                "bullet_number": 1,
                "action": "rewrite",
                "accepted_text": "Accepted concise wording.",
            },
        ]
        with patch("session_ledger.os.replace", wraps=os.replace) as replace:
            snapshot = apply_decision_batch(
                self.repository,
                "example-role",
                decisions,
                current_entry_number=2,
                confirmed_facts=["Confirmed fact"],
            )
        self.assertEqual(1, replace.call_count)
        self.assertEqual(2, snapshot["current_entry"]["entry_number"])
        self.assertEqual("rewrite", snapshot["current_entry"]["bullets"][0]["decision"]["action"])
        self.assertEqual(["Confirmed fact"], snapshot["confirmed_facts"])

    def test_undo_reverts_the_complete_batch(self) -> None:
        project_entry = project_selection_snapshot(self.repository, "example-role")["projects"][0][
            "entry_number"
        ]
        apply_decision_batch(
            self.repository,
            "example-role",
            [{"entry_number": 1, "bullet_number": 1, "action": "remove"}],
            project_decisions=[{"entry_number": project_entry, "action": "include"}],
            confirmed_facts=["Temporary fact"],
        )
        snapshot = undo_last_batch(self.repository, "example-role")
        self.assertIsNone(snapshot["current_entry"]["bullets"][0]["decision"])
        self.assertEqual([], snapshot["confirmed_facts"])
        projects = project_selection_snapshot(self.repository, "example-role")["projects"]
        self.assertIsNone(projects[0]["project_decision"])

    def test_cli_batches_decisions_and_returns_active_entry(self) -> None:
        project_entry = project_selection_snapshot(self.repository, "example-role")["projects"][0][
            "entry_number"
        ]
        result = subprocess.run(
            [
                sys.executable,
                str(SKILL_SCRIPTS / "session_ledger.py"),
                "--repository",
                str(self.repository),
                "update",
                "example-role",
                "--decision",
                "1",
                "1",
                "keep",
                "-",
                "--project-decision",
                str(project_entry),
                "include",
                "--current-entry",
                "2",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        snapshot = json.loads(result.stdout)
        self.assertEqual("ready", snapshot["status"])
        self.assertEqual(2, snapshot["current_entry"]["entry_number"])
        projects = project_selection_snapshot(self.repository, "example-role")["projects"]
        self.assertEqual("include", projects[0]["project_decision"]["action"])

    def test_session_is_written_under_gitignored_directory(self) -> None:
        expected = self.repository.resolve() / ".resume" / "sessions" / "example-role.json"
        self.assertEqual(expected, ledger_path(self.repository, "example-role"))
        self.assertTrue(expected.is_file())

    def test_list_labels_pre_schema_sessions_as_legacy(self) -> None:
        legacy_path = self.repository / ".resume" / "sessions" / "legacy-role.json"
        legacy_path.write_text(
            json.dumps({"id": "legacy-role", "target": "legacy-target", "complete": True}),
            encoding="utf-8",
        )
        sessions = list_sessions(self.repository)
        legacy = next(item for item in sessions if item["session_id"] == "legacy-role")
        self.assertEqual("legacy", legacy["status"])
        self.assertTrue(legacy["complete"])


if __name__ == "__main__":
    unittest.main()
