"""Atomic session state for the conversational resume-tailoring skill."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from resume_validation import MASTER_SOURCE_RELATIVE_PATH, parse_resume, tex_to_text


SCHEMA_VERSION = 1
SESSION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")
DECISION_ACTIONS = {"keep", "rewrite", "remove", "clear"}


class SessionLedgerError(ValueError):
    """Raised when session state cannot be read or updated safely."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _validate_slug(value: str, label: str) -> str:
    if not SESSION_ID_RE.fullmatch(value):
        raise SessionLedgerError(
            f"{label} must be lowercase, hyphenated, and at most 80 characters: {value!r}"
        )
    return value


def _sessions_directory(repository: Path) -> Path:
    return repository.resolve() / ".resume" / "sessions"


def ledger_path(repository: Path, session_id: str) -> Path:
    return _sessions_directory(repository) / f"{_validate_slug(session_id, 'Session ID')}.json"


def _master_path(repository: Path) -> Path:
    path = repository.resolve() / MASTER_SOURCE_RELATIVE_PATH
    if not path.is_file():
        raise SessionLedgerError(f"Master resume was not found: {path}")
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as destination:
            json.dump(payload, destination, indent=2, ensure_ascii=False)
            destination.write("\n")
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _entry_payload(source: str) -> list[dict[str, Any]]:
    entries = []
    for entry_number, entry in enumerate(parse_resume(source), start=1):
        entries.append(
            {
                "entry_number": entry_number,
                "section": entry.section,
                "title": entry.title,
                "subtitle": entry.subtitle,
                "date": entry.date,
                "bullets": [
                    {
                        "bullet_number": bullet_number,
                        "source_latex": bullet.text,
                        "source_text": tex_to_text(bullet.text),
                        "is_metadata": bullet.is_metadata,
                        "decision": None,
                    }
                    for bullet_number, bullet in enumerate(entry.bullets, start=1)
                ],
            }
        )
    return entries


def create_session(
    repository: Path,
    session_id: str,
    target_slug: str,
    job_description: str,
) -> Path:
    """Create a ledger from one complete master-resume read."""
    _validate_slug(target_slug, "Target slug")
    path = ledger_path(repository, session_id)
    if path.exists():
        raise SessionLedgerError(f"Session already exists: {path}")
    if not job_description.strip():
        raise SessionLedgerError("Job description cannot be empty")

    master_path = _master_path(repository)
    master_source = master_path.read_text(encoding="utf-8")
    created_at = _now()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "target_slug": target_slug,
        "job_description": job_description.strip(),
        "master": {
            "path": str(MASTER_SOURCE_RELATIVE_PATH),
            "sha256": _sha256(master_path),
        },
        "entries": _entry_payload(master_source),
        "current_entry_number": 1,
        "confirmed_facts": [],
        "batches": [],
        "created_at": created_at,
        "updated_at": created_at,
    }
    _atomic_write(path, payload)
    return path


def _load_session(repository: Path, session_id: str) -> tuple[Path, dict[str, Any]]:
    path = ledger_path(repository, session_id)
    if not path.is_file():
        raise SessionLedgerError(f"Session was not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        raise SessionLedgerError(f"Session ledger is unreadable: {path}") from error
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise SessionLedgerError(f"Unsupported session schema in {path}")
    return path, payload


def _master_status(repository: Path, payload: dict[str, Any]) -> tuple[str, str]:
    current_hash = _sha256(_master_path(repository))
    expected_hash = payload["master"]["sha256"]
    return ("ready" if current_hash == expected_hash else "stale", current_hash)


def _compact_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "entry_number": entry["entry_number"],
        "section": entry["section"],
        "title": entry["title"],
        "subtitle": entry["subtitle"],
        "date": entry["date"],
        "bullets": [
            {
                "bullet_number": bullet["bullet_number"],
                "source_text": bullet["source_text"],
                "is_metadata": bullet["is_metadata"],
                "decision": bullet["decision"],
            }
            for bullet in entry["bullets"]
        ],
    }


def _ready_snapshot(
    payload: dict[str, Any],
    current_hash: str,
    *,
    include_job_description: bool = False,
) -> dict[str, Any]:
    entry_number = payload["current_entry_number"]
    entry = payload["entries"][entry_number - 1]
    snapshot = {
        "status": "ready",
        "session_id": payload["session_id"],
        "target_slug": payload["target_slug"],
        "master_sha256": current_hash,
        "entry_count": len(payload["entries"]),
        "current_entry": _compact_entry(entry),
        "confirmed_facts": payload["confirmed_facts"],
        "updated_at": payload["updated_at"],
    }
    if include_job_description:
        snapshot["job_description"] = payload["job_description"]
    return snapshot


def session_snapshot(
    repository: Path,
    session_id: str,
    *,
    include_job_description: bool = False,
) -> dict[str, Any]:
    """Return only the active entry after verifying the master hash."""
    _, payload = _load_session(repository, session_id)
    status, current_hash = _master_status(repository, payload)
    if status == "stale":
        return {
            "status": "stale",
            "session_id": session_id,
            "expected_master_sha256": payload["master"]["sha256"],
            "current_master_sha256": current_hash,
            "message": "Master resume changed; reread it and reconcile the session before continuing.",
        }
    return _ready_snapshot(
        payload,
        current_hash,
        include_job_description=include_job_description,
    )


def apply_decision_batch(
    repository: Path,
    session_id: str,
    decisions: list[dict[str, Any]],
    *,
    current_entry_number: int | None = None,
    confirmed_facts: list[str] | None = None,
) -> dict[str, Any]:
    """Persist every decision from one user message with one atomic replacement."""
    path, payload = _load_session(repository, session_id)
    status, current_hash = _master_status(repository, payload)
    if status != "ready":
        raise SessionLedgerError(
            "Master resume changed; reread it and reconcile the session before saving decisions"
        )

    changes = []
    for requested in decisions:
        entry_number = int(requested["entry_number"])
        bullet_number = int(requested["bullet_number"])
        action = str(requested["action"]).lower()
        accepted_text = requested.get("accepted_text")
        if action not in DECISION_ACTIONS:
            raise SessionLedgerError(f"Unsupported decision action: {action}")
        if not 1 <= entry_number <= len(payload["entries"]):
            raise SessionLedgerError(f"Entry number is out of range: {entry_number}")
        entry = payload["entries"][entry_number - 1]
        if not 1 <= bullet_number <= len(entry["bullets"]):
            raise SessionLedgerError(
                f"Bullet number is out of range for entry {entry_number}: {bullet_number}"
            )
        if action == "rewrite" and not str(accepted_text or "").strip():
            raise SessionLedgerError("A rewrite decision requires accepted text")

        bullet = entry["bullets"][bullet_number - 1]
        before = copy.deepcopy(bullet["decision"])
        if action == "clear":
            after = None
        elif action == "keep":
            after = {
                "action": "keep",
                "accepted_text": bullet["source_text"],
                "decided_at": _now(),
            }
        elif action == "remove":
            after = {"action": "remove", "accepted_text": None, "decided_at": _now()}
        else:
            after = {
                "action": "rewrite",
                "accepted_text": str(accepted_text).strip(),
                "decided_at": _now(),
            }
        bullet["decision"] = after
        changes.append(
            {
                "entry_number": entry_number,
                "bullet_number": bullet_number,
                "before": before,
                "after": copy.deepcopy(after),
            }
        )

    previous_entry_number = payload["current_entry_number"]
    if current_entry_number is not None:
        if not 1 <= current_entry_number <= len(payload["entries"]):
            raise SessionLedgerError(f"Current entry number is out of range: {current_entry_number}")
        payload["current_entry_number"] = current_entry_number

    added_facts = []
    for fact in confirmed_facts or []:
        normalized = fact.strip()
        if normalized and normalized not in payload["confirmed_facts"]:
            payload["confirmed_facts"].append(normalized)
            added_facts.append(normalized)

    if not changes and not added_facts and current_entry_number is None:
        raise SessionLedgerError("The batch does not contain any changes")

    saved_at = _now()
    payload["batches"].append(
        {
            "saved_at": saved_at,
            "previous_entry_number": previous_entry_number,
            "current_entry_number": payload["current_entry_number"],
            "decisions": changes,
            "confirmed_facts_added": added_facts,
        }
    )
    payload["updated_at"] = saved_at
    _atomic_write(path, payload)
    return _ready_snapshot(payload, current_hash)


def undo_last_batch(repository: Path, session_id: str) -> dict[str, Any]:
    """Undo the most recent user-message batch with one atomic replacement."""
    path, payload = _load_session(repository, session_id)
    status, current_hash = _master_status(repository, payload)
    if status != "ready":
        raise SessionLedgerError("Master resume changed; reconcile the session before undoing")
    if not payload["batches"]:
        raise SessionLedgerError("There is no saved batch to undo")

    batch = payload["batches"].pop()
    for change in reversed(batch["decisions"]):
        entry = payload["entries"][change["entry_number"] - 1]
        entry["bullets"][change["bullet_number"] - 1]["decision"] = change["before"]
    for fact in batch["confirmed_facts_added"]:
        if fact in payload["confirmed_facts"]:
            payload["confirmed_facts"].remove(fact)
    payload["current_entry_number"] = batch["previous_entry_number"]
    payload["updated_at"] = _now()
    _atomic_write(path, payload)
    return _ready_snapshot(payload, current_hash)


def list_sessions(repository: Path) -> list[dict[str, Any]]:
    sessions = []
    current_master_hash = _sha256(_master_path(repository))
    for path in sorted(_sessions_directory(repository).glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("schema_version") != SCHEMA_VERSION:
                sessions.append(
                    {
                        "session_id": payload.get("session_id", payload.get("id", path.stem)),
                        "target_slug": payload.get("target_slug", payload.get("target")),
                        "status": "legacy",
                        "complete": payload.get("complete"),
                    }
                )
                continue
            status = (
                "ready" if payload["master"]["sha256"] == current_master_hash else "stale"
            )
            sessions.append(
                {
                    "session_id": payload["session_id"],
                    "target_slug": payload["target_slug"],
                    "status": status,
                    "current_entry_number": payload["current_entry_number"],
                    "entry_count": len(payload["entries"]),
                    "updated_at": payload["updated_at"],
                }
            )
        except (KeyError, OSError, json.JSONDecodeError, SessionLedgerError):
            sessions.append({"session_id": path.stem, "status": "invalid"})
    return sessions


def _repository(value: str) -> Path:
    return Path(value).resolve()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=".", type=_repository)
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="Create a new session ledger")
    start.add_argument("session_id")
    start.add_argument("--target-slug", required=True)
    start.add_argument("--job-description-file", required=True, type=Path)

    show = subparsers.add_parser("show", help="Verify and return the active entry")
    show.add_argument("session_id")
    show.add_argument("--include-job-description", action="store_true")

    update = subparsers.add_parser("update", help="Atomically save one user-message batch")
    update.add_argument("session_id")
    update.add_argument(
        "--decision",
        action="append",
        nargs=4,
        metavar=("ENTRY", "BULLET", "ACTION", "TEXT_OR_DASH"),
        default=[],
    )
    update.add_argument("--current-entry", type=int)
    update.add_argument("--confirmed-fact", action="append", default=[])

    undo = subparsers.add_parser("undo", help="Undo the last saved batch")
    undo.add_argument("session_id")

    subparsers.add_parser("list", help="List available sessions")
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    try:
        if args.command == "start":
            job_description = args.job_description_file.read_text(encoding="utf-8")
            path = create_session(args.repository, args.session_id, args.target_slug, job_description)
            output: Any = {"status": "created", "ledger": str(path)}
        elif args.command == "show":
            output = session_snapshot(
                args.repository,
                args.session_id,
                include_job_description=args.include_job_description,
            )
        elif args.command == "update":
            decisions = [
                {
                    "entry_number": int(entry),
                    "bullet_number": int(bullet),
                    "action": action,
                    "accepted_text": None if text == "-" else text,
                }
                for entry, bullet, action, text in args.decision
            ]
            output = apply_decision_batch(
                args.repository,
                args.session_id,
                decisions,
                current_entry_number=args.current_entry,
                confirmed_facts=args.confirmed_fact,
            )
        elif args.command == "undo":
            output = undo_last_batch(args.repository, args.session_id)
        else:
            output = list_sessions(args.repository)
        print(json.dumps(output, indent=2, ensure_ascii=False))
        return 3 if isinstance(output, dict) and output.get("status") == "stale" else 0
    except (OSError, SessionLedgerError, ValueError) as error:
        print(json.dumps({"status": "error", "message": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
