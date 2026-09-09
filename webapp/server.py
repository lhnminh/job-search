#!/usr/bin/env python3
"""Local-only HTTP server for the Resume Tailoring Workspace."""

from __future__ import annotations

import argparse
import json
import mimetypes
import re
import shutil
import sys
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = Path(__file__).resolve().parent / "static"
SKILL_SCRIPTS = REPOSITORY_ROOT / ".agents" / "skills" / "tailor-resume" / "scripts"
sys.path.insert(0, str(SKILL_SCRIPTS))

from workspace import WorkspaceError, WorkspaceStore  # noqa: E402


class ResumeAppHandler(SimpleHTTPRequestHandler):
    server_version = "ResumeWorkspace/0.1"
    store = WorkspaceStore(REPOSITORY_ROOT)

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, directory=str(STATIC_ROOT), **kwargs)

    def _send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(encoded)

    def _send_file(self, path: Path) -> None:
        if not path.is_file():
            self._send_json({"status": "error", "message": "File not found"}, HTTPStatus.NOT_FOUND)
            return
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def end_headers(self) -> None:
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; frame-src 'self'; object-src 'self'; base-uri 'none'; form-action 'self'",
        )
        super().end_headers()

    def _request_json(self) -> dict[str, object]:
        if self.headers.get("X-Resume-App") != "local":
            raise WorkspaceError("The local application header is required.")
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise WorkspaceError("This request did not come from the local application.")
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise WorkspaceError("The request size is invalid.") from error
        if length <= 0 or length > 2_000_000:
            raise WorkspaceError("The request must contain no more than 2 MB of JSON.")
        try:
            payload = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise WorkspaceError("The request body must be valid JSON.") from error
        if not isinstance(payload, dict):
            raise WorkspaceError("The request body must be a JSON object.")
        return payload

    @staticmethod
    def _session_route(path: str) -> tuple[str, str] | None:
        match = re.fullmatch(r"/api/sessions/([a-z0-9][a-z0-9-]{0,79})(?:/([a-z.-]+))?", path)
        if not match:
            return None
        return match.group(1), match.group(2) or "detail"

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            if path == "/api/health":
                self._send_json({"status": "ok"})
                return
            if path == "/api/master":
                self._send_json(self.store.master())
                return
            if path == "/api/master/pdf":
                self._send_file(REPOSITORY_ROOT / "master" / "Morgan_Le_Resume.pdf")
                return
            if path == "/api/sessions":
                self._send_json({"status": "ready", "sessions": self.store.list_sessions()})
                return
            if path == "/api/settings":
                self._send_json(
                    {
                        "status": "ready",
                        "repository": str(REPOSITORY_ROOT),
                        "session_data": str(REPOSITORY_ROOT / ".resume" / "webapp"),
                        "network": "Localhost only",
                        "ai_mode": "Active Codex task via workspace bridge",
                        "tectonic": bool(shutil.which("tectonic")),
                        "pdf_renderer": bool(shutil.which("pdftoppm")),
                    }
                )
                return
            session_route = self._session_route(path)
            if session_route:
                session_id, action = session_route
                if action == "detail":
                    self._send_json(self.store.get_session(session_id))
                    return
                if action == "context":
                    self._send_json(self.store.suggestion_context(session_id))
                    return
                if action == "preview.pdf":
                    self._send_file(self.store.preview_path(session_id))
                    return
            super().do_GET()
        except WorkspaceError as error:
            self._send_json({"status": "error", "message": str(error)}, HTTPStatus.BAD_REQUEST)
        except Exception as error:  # local boundary: return a useful UI error
            self._send_json(
                {"status": "error", "message": str(error)},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            payload = self._request_json()
            if path == "/api/sessions":
                session = self.store.create_session(
                    company=str(payload.get("company") or ""),
                    role=str(payload.get("role") or ""),
                    job_description=str(payload.get("job_description") or ""),
                    job_url=str(payload.get("job_url") or ""),
                    requested_slug=str(payload.get("slug") or ""),
                )
                self._send_json(session, HTTPStatus.CREATED)
                return
            session_route = self._session_route(path)
            if not session_route:
                self._send_json({"status": "error", "message": "Unknown endpoint"}, HTTPStatus.NOT_FOUND)
                return
            session_id, action = session_route
            if action == "analysis":
                result = self.store.save_analysis(
                    session_id,
                    requirements=list(payload.get("requirements") or []),
                    bullet_suggestions=list(payload.get("bullet_suggestions") or []),
                    project_suggestions=list(payload.get("project_suggestions") or []),
                )
            elif action == "decisions":
                result = self.store.apply_decisions(
                    session_id,
                    bullet_decisions=list(payload.get("bullet_decisions") or []),
                    project_decisions=list(payload.get("project_decisions") or []),
                    confirmed_facts=list(payload.get("confirmed_facts") or []),
                )
            elif action == "revision-request":
                result = self.store.request_revision(
                    session_id,
                    entry_number=int(payload.get("entry_number") or 0),
                    bullet_number=int(payload.get("bullet_number") or 0),
                    instruction=str(payload.get("instruction") or ""),
                )
            elif action == "revision":
                result = self.store.save_revision(
                    session_id,
                    request_id=str(payload.get("request_id") or ""),
                    suggestion=dict(payload.get("suggestion") or {}),
                )
            elif action == "undo":
                result = self.store.undo(session_id)
            elif action == "archive":
                result = self.store.archive_session(session_id)
            elif action == "reconcile":
                result = self.store.reconcile_session(session_id)
            elif action == "preview":
                result = self.store.build_preview(session_id)
            elif action == "export":
                result = self.store.export(session_id, overwrite=bool(payload.get("overwrite")))
            else:
                self._send_json({"status": "error", "message": "Unknown endpoint"}, HTTPStatus.NOT_FOUND)
                return
            self._send_json(result)
        except WorkspaceError as error:
            self._send_json({"status": "error", "message": str(error)}, HTTPStatus.BAD_REQUEST)
        except Exception as error:
            self._send_json(
                {"status": "error", "message": str(error)},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def log_message(self, format: str, *args: object) -> None:
        sys.stderr.write(f"[resume-app] {format % args}\n")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4173)
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("The resume app is local-only; bind to localhost or a loopback address.")
    server = ThreadingHTTPServer((args.host, args.port), ResumeAppHandler)
    print(f"Resume Tailoring Workspace: http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
