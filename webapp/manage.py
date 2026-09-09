#!/usr/bin/env python3
"""Bridge the active Codex conversation to local resume-workspace sessions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from workspace import REPOSITORY_ROOT, WorkspaceError, WorkspaceStore


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=REPOSITORY_ROOT)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("sessions", help="List local web-app tailoring sessions")
    context = subparsers.add_parser("context", help="Read one complete suggestion context")
    context.add_argument("session_id")
    submit = subparsers.add_parser("submit", help="Save a complete suggestion set")
    submit.add_argument("session_id")
    submit.add_argument("analysis_file", type=Path)
    revise = subparsers.add_parser("revise", help="Fulfill one pending revision request")
    revise.add_argument("session_id")
    revise.add_argument("request_id")
    revise.add_argument("suggestion_file", type=Path)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    store = WorkspaceStore(args.repository)
    try:
        if args.command == "sessions":
            result = {"status": "ready", "sessions": store.list_sessions()}
        elif args.command == "context":
            result = store.suggestion_context(args.session_id)
        elif args.command == "submit":
            analysis = json.loads(args.analysis_file.read_text(encoding="utf-8"))
            result = store.save_analysis(
                args.session_id,
                requirements=list(analysis.get("requirements") or []),
                bullet_suggestions=list(analysis.get("bullet_suggestions") or []),
                project_suggestions=list(analysis.get("project_suggestions") or []),
            )
        else:
            suggestion = json.loads(args.suggestion_file.read_text(encoding="utf-8"))
            result = store.save_revision(
                args.session_id,
                request_id=args.request_id,
                suggestion=suggestion,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, json.JSONDecodeError, WorkspaceError, ValueError) as error:
        print(json.dumps({"status": "error", "message": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
