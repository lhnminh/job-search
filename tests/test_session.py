from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from resume_cli.session import Session, SessionStore


class SessionStoreTests(unittest.TestCase):
    def test_round_trip_and_latest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SessionStore(Path(directory))
            session = Session.create(mode="review", target=".", job_description="")
            session.working_tex = "resume"
            session.thread_id = "thread-123"
            session.cursor = 4
            store.save(session)
            loaded = store.load(session.id)
            self.assertEqual("resume", loaded.working_tex)
            self.assertEqual("thread-123", loaded.thread_id)
            self.assertEqual(4, loaded.cursor)
            self.assertEqual(session.id, store.latest().id)
            loaded.complete = True
            store.save(loaded)
            self.assertEqual([], store.unfinished())

    def test_rejects_path_like_session_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = SessionStore(Path(directory))
            with self.assertRaises(ValueError):
                store.load("../../other")


if __name__ == "__main__":
    unittest.main()
