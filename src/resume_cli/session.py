from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class Session:
    id: str
    mode: str
    target: str
    job_description: str
    created_at: str
    updated_at: str
    thread_id: str | None = None
    cursor: int = 0
    complete: bool = False
    working_tex: str = ""
    original_hash: str = ""
    history: list[str] = field(default_factory=list)
    source_appends: list[dict[str, str]] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, *, mode: str, target: str, job_description: str) -> "Session":
        timestamp = _now()
        return cls(
            id=f"{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}",
            mode=mode,
            target=target,
            job_description=job_description,
            created_at=timestamp,
            updated_at=timestamp,
        )


class SessionStore:
    def __init__(self, repo_root: Path):
        self.directory = repo_root / ".resume" / "sessions"

    def save(self, session: Session) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        session.updated_at = _now()
        path = self.directory / f"{session.id}.json"
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(asdict(session), indent=2, ensure_ascii=False) + "\n")
        os.replace(temporary, path)
        return path

    def load(self, session_id: str) -> Session:
        if not re.fullmatch(r"[A-Za-z0-9-]+", session_id):
            raise ValueError(f"Invalid session ID: {session_id}")
        path = self.directory / f"{session_id}.json"
        return Session(**json.loads(path.read_text()))

    def unfinished(self) -> list[Session]:
        if not self.directory.exists():
            return []
        sessions: list[Session] = []
        for path in self.directory.glob("*.json"):
            try:
                session = Session(**json.loads(path.read_text()))
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                continue
            if not session.complete:
                sessions.append(session)
        return sorted(sessions, key=lambda item: item.updated_at, reverse=True)

    def latest(self) -> Session:
        sessions = self.unfinished()
        if not sessions:
            raise FileNotFoundError("No unfinished resume sessions were found")
        return sessions[0]
