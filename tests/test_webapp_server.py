from __future__ import annotations

import json
import re
import shutil
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "webapp"))

from server import ResumeAppHandler  # noqa: E402
from workspace import WorkspaceStore  # noqa: E402


class ResumeAppRouteTests(unittest.TestCase):
    def test_matches_safe_session_routes(self) -> None:
        self.assertEqual(
            ("example-role", "analysis"),
            ResumeAppHandler._session_route("/api/sessions/example-role/analysis"),
        )
        self.assertEqual(
            ("example-role", "preview.pdf"),
            ResumeAppHandler._session_route("/api/sessions/example-role/preview.pdf"),
        )

    def test_rejects_path_traversal_routes(self) -> None:
        self.assertIsNone(ResumeAppHandler._session_route("/api/sessions/../../master"))
        self.assertIsNone(ResumeAppHandler._session_route("/api/sessions/example_role"))

    def test_static_interface_has_unique_ids_and_bound_controls(self) -> None:
        html = (REPOSITORY_ROOT / "webapp" / "static" / "index.html").read_text(
            encoding="utf-8"
        )
        javascript = (REPOSITORY_ROOT / "webapp" / "static" / "app.js").read_text(
            encoding="utf-8"
        )
        identifiers = re.findall(r'\bid="([a-z0-9-]+)"', html)
        self.assertEqual(len(identifiers), len(set(identifiers)))
        bound_ids = set(
            re.findall(r'document\.querySelector\(["\']#([a-z0-9-]+)["\']\)', javascript)
        )
        self.assertEqual(set(), bound_ids - set(identifiers))
        for required in {
            "resume-content",
            "job-form",
            "suggestion-content",
            "decision-overview",
            "other-dialog",
            "build-preview",
            "export-button",
        }:
            self.assertIn(required, identifiers)


class _ServerStub:
    server_name = "localhost"
    server_port = 4173


class ResumeAppHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.repository = Path(self.temporary_directory.name)
        (self.repository / "master").mkdir()
        shutil.copy(REPOSITORY_ROOT / "master" / "_resume.tex", self.repository / "master")

        class TemporaryResumeAppHandler(ResumeAppHandler):
            store = WorkspaceStore(self.repository)

        self.handler = TemporaryResumeAppHandler

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _request(self, request: bytes) -> tuple[str, dict[str, str], bytes]:
        client, server = socket.socketpair()
        try:
            client.sendall(request)
            client.shutdown(socket.SHUT_WR)

            def serve() -> None:
                try:
                    self.handler(server, ("127.0.0.1", 43120), _ServerStub())
                finally:
                    server.shutdown(socket.SHUT_WR)

            thread = threading.Thread(target=serve)
            thread.start()
            chunks = []
            while True:
                chunk = client.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive(), "The HTTP handler did not finish.")
        finally:
            client.close()
            server.close()
        head, body = b"".join(chunks).split(b"\r\n\r\n", 1)
        lines = head.decode("iso-8859-1").split("\r\n")
        headers = dict(line.split(": ", 1) for line in lines[1:])
        return lines[0], headers, body

    def test_health_endpoint_uses_security_headers(self) -> None:
        status, headers, body = self._request(
            b"GET /api/health HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n"
        )
        self.assertIn("200 OK", status)
        self.assertEqual("no-store", headers["Cache-Control"])
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual({"status": "ok"}, json.loads(body))

    def test_session_creation_persists_through_the_real_http_handler(self) -> None:
        payload = json.dumps(
            {
                "company": "Example Company",
                "role": "Data Scientist",
                "job_description": "Build and evaluate production machine-learning systems, reliable data pipelines, and decision-ready analysis with cross-functional teams.",
            }
        ).encode("utf-8")
        request = (
            b"POST /api/sessions HTTP/1.1\r\n"
            b"Host: localhost\r\n"
            b"X-Resume-App: local\r\n"
            b"Content-Type: application/json\r\n"
            + f"Content-Length: {len(payload)}\r\n".encode("ascii")
            + b"Connection: close\r\n\r\n"
            + payload
        )
        status, _, body = self._request(request)
        session = json.loads(body)
        self.assertIn("201 Created", status)
        self.assertEqual("example-company-data-scientist", session["session_id"])
        self.assertTrue(
            (self.repository / ".resume" / "webapp" / "sessions" / "example-company-data-scientist.json").is_file()
        )

    def test_mutation_without_local_header_is_rejected(self) -> None:
        payload = b"{}"
        request = (
            b"POST /api/sessions HTTP/1.1\r\nHost: localhost\r\n"
            + f"Content-Length: {len(payload)}\r\n".encode("ascii")
            + b"Connection: close\r\n\r\n"
            + payload
        )
        status, _, body = self._request(request)
        self.assertIn("400 Bad Request", status)
        self.assertIn("local application header", json.loads(body)["message"])


if __name__ == "__main__":
    unittest.main()
