"""Deterministic local state, source assembly, and PDF workflow for the web app."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = REPOSITORY_ROOT / ".agents" / "skills" / "tailor-resume" / "scripts"

import sys

sys.path.insert(0, str(SKILL_SCRIPTS))

from resume_validation import (  # noqa: E402
    ITEM_RE,
    ResumeValidationError,
    _entry_arguments,
    parse_resume,
    tex_to_text,
    validate_tailored_completeness,
    validate_tailored_tex,
    verify_pdf,
)


SESSION_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")
SUGGESTION_ACTIONS = {"keep", "rewrite", "remove", "ask"}
PROJECT_ACTIONS = {"include", "exclude"}
DECISION_ACTIONS = {"keep", "rewrite", "remove"}
REQUIREMENT_CATEGORIES = {"responsibility", "required", "preferred", "keyword", "eligibility"}


class WorkspaceError(ValueError):
    """Raised when a local workspace operation cannot be completed safely."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as destination:
            json.dump(payload, destination, ensure_ascii=False, indent=2)
            destination.write("\n")
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as destination:
            destination.write(text)
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as destination:
            destination.write(data)
            destination.flush()
            os.fsync(destination.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return value[:80].rstrip("-") or "tailored-resume"


def _validate_slug(value: str) -> str:
    if not SESSION_ID_RE.fullmatch(value):
        raise WorkspaceError("The session name must be lowercase, hyphenated, and under 80 characters.")
    return value


def _entry_records(source: str) -> list[dict[str, Any]]:
    records = []
    for entry_number, entry in enumerate(parse_resume(source), start=1):
        records.append(
            {
                "entry_number": entry_number,
                "section": entry.section,
                "title": entry.title,
                "subtitle": entry.subtitle,
                "date": entry.date,
                "is_project": "project" in entry.section.casefold(),
                "project_decision": None,
                "bullets": [
                    {
                        "bullet_number": bullet_number,
                        "source_text": tex_to_text(bullet.text),
                        "source_latex": bullet.text,
                        "is_metadata": bullet.is_metadata,
                        "decision": None,
                    }
                    for bullet_number, bullet in enumerate(entry.bullets, start=1)
                ],
            }
        )
    return records


def _public_session(payload: dict[str, Any], current_master_hash: str) -> dict[str, Any]:
    public = copy.deepcopy(payload)
    for entry in public["entries"]:
        for bullet in entry["bullets"]:
            bullet.pop("source_latex", None)
    public["status"] = (
        "ready" if payload["master"]["sha256"] == current_master_hash else "stale"
    )
    public["decision_counts"] = _decision_counts(payload)
    public["stage"] = _session_stage(payload, public["decision_counts"])
    public["next_unresolved"] = _next_unresolved(payload)
    return public


def _decision_counts(payload: dict[str, Any]) -> dict[str, int]:
    counts = {
        "all": 0,
        "unresolved": 0,
        "accepted": 0,
        "kept": 0,
        "removed": 0,
        "needs_confirmation": 0,
    }
    suggestions = payload.get("suggestions") or {}
    bullet_suggestions = {
        (item["entry_number"], item["bullet_number"]): item
        for item in suggestions.get("bullets", [])
    }
    project_suggestions = {
        item["entry_number"]: item for item in suggestions.get("projects", [])
    }
    for entry in payload["entries"]:
        if entry["is_project"]:
            if entry["entry_number"] in project_suggestions:
                counts["all"] += 1
                project_decision = entry["project_decision"]
                if project_decision is None:
                    counts["unresolved"] += 1
                elif project_decision["action"] == "exclude":
                    counts["removed"] += 1
                else:
                    counts["accepted"] += 1
            if (entry.get("project_decision") or {}).get("action") != "include":
                continue
        for bullet in entry["bullets"]:
            suggestion = bullet_suggestions.get(
                (entry["entry_number"], bullet["bullet_number"])
            )
            if suggestion is None:
                continue
            counts["all"] += 1
            decision = bullet["decision"]
            if decision is None:
                counts["unresolved"] += 1
                if suggestion["action"] == "ask":
                    counts["needs_confirmation"] += 1
            elif decision["action"] == "keep":
                counts["kept"] += 1
            elif decision["action"] == "remove":
                counts["removed"] += 1
            else:
                counts["accepted"] += 1
    return counts


def _session_stage(payload: dict[str, Any], counts: dict[str, int]) -> str:
    if payload.get("export"):
        return "Exported"
    if not payload.get("suggestions"):
        return "Preparing suggestions"
    if counts["unresolved"]:
        return "Reviewing suggestions"
    preview = payload.get("preview") or {}
    if preview.get("report", {}).get("pages") == 1:
        return "Final review"
    return "Page fit"


def _next_unresolved(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not payload.get("suggestions"):
        return None
    for entry in payload["entries"]:
        if entry["is_project"]:
            if entry.get("project_decision") is None:
                return {"kind": "project", "entry_number": entry["entry_number"]}
            if entry["project_decision"]["action"] == "exclude":
                continue
        for bullet in entry["bullets"]:
            if bullet.get("decision") is None:
                return {
                    "kind": "bullet",
                    "entry_number": entry["entry_number"],
                    "bullet_number": bullet["bullet_number"],
                }
    return None


class WorkspaceStore:
    """Owns all web-app state beneath the repository's gitignored .resume folder."""

    def __init__(self, repository: Path = REPOSITORY_ROOT) -> None:
        self.repository = repository.resolve()
        self.master_path = self.repository / "master" / "_resume.tex"
        self.master_pdf_path = self.repository / "master" / "Morgan_Le_Resume.pdf"
        self.sessions_directory = self.repository / ".resume" / "webapp" / "sessions"
        self.archive_directory = self.repository / ".resume" / "webapp" / "archive"
        self.previews_directory = self.repository / ".resume" / "webapp" / "previews"

    def master(self) -> dict[str, Any]:
        if not self.master_path.is_file():
            raise WorkspaceError("The master resume source could not be found.")
        source = self.master_path.read_text(encoding="utf-8")
        entries = _entry_records(source)
        for entry in entries:
            for bullet in entry["bullets"]:
                bullet.pop("source_latex", None)
                bullet.pop("decision", None)
            entry.pop("project_decision", None)
        return {
            "status": "ready",
            "sha256": _sha256(self.master_path),
            "entries": entries,
            "entry_count": len(entries),
            "pdf": {
                "available": self.master_pdf_path.is_file(),
                "url": "/api/master/pdf" if self.master_pdf_path.is_file() else None,
                "updated_at": (
                    self.master_pdf_path.stat().st_mtime if self.master_pdf_path.is_file() else None
                ),
            },
        }

    def _path(self, session_id: str) -> Path:
        return self.sessions_directory / f"{_validate_slug(session_id)}.json"

    def _load(self, session_id: str) -> tuple[Path, dict[str, Any]]:
        path = self._path(session_id)
        if not path.is_file():
            raise WorkspaceError("The tailoring session could not be found.")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise WorkspaceError("The tailoring session is unreadable.") from error
        if payload.get("schema_version") != 1:
            raise WorkspaceError("The tailoring session uses an unsupported format.")
        return path, payload

    def _current_hash(self) -> str:
        return _sha256(self.master_path)

    def _require_fresh(self, payload: dict[str, Any]) -> str:
        current_hash = self._current_hash()
        if payload["master"]["sha256"] != current_hash:
            raise WorkspaceError(
                "The master resume changed after this session started. Reconcile it before continuing."
            )
        return current_hash

    def create_session(
        self,
        *,
        company: str,
        role: str,
        job_description: str,
        job_url: str = "",
        requested_slug: str = "",
    ) -> dict[str, Any]:
        company = company.strip()
        role = role.strip()
        job_description = job_description.strip()
        if not company or not role:
            raise WorkspaceError("Company and role are required.")
        if len(job_description) < 80:
            raise WorkspaceError("Paste the complete job description before tailoring.")
        base = _validate_slug(requested_slug) if requested_slug else _slugify(f"{company}-{role}")
        session_id = base
        suffix = 2
        while self._path(session_id).exists() or (self.repository / session_id).exists():
            ending = f"-{suffix}"
            session_id = f"{base[: 80 - len(ending)].rstrip('-')}{ending}"
            suffix += 1
        source = self.master_path.read_text(encoding="utf-8")
        timestamp = _now()
        payload = {
            "schema_version": 1,
            "session_id": session_id,
            "target_slug": session_id,
            "job": {
                "company": company,
                "role": role,
                "url": job_url.strip(),
                "description": job_description,
            },
            "master": {"path": "master/_resume.tex", "sha256": _sha256(self.master_path)},
            "entries": _entry_records(source),
            "requirements": [],
            "suggestions": None,
            "confirmed_facts": [],
            "revision_requests": [],
            "history": [],
            "preview": None,
            "export": None,
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        path = self._path(session_id)
        _atomic_json(path, payload)
        return _public_session(payload, payload["master"]["sha256"])

    def list_sessions(self) -> list[dict[str, Any]]:
        self.sessions_directory.mkdir(parents=True, exist_ok=True)
        current_hash = self._current_hash()
        sessions = []
        for path in sorted(self.sessions_directory.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if payload.get("schema_version") != 1:
                    continue
                counts = _decision_counts(payload)
                sessions.append(
                    {
                        "session_id": payload["session_id"],
                        "target_slug": payload["target_slug"],
                        "job": payload["job"],
                        "status": (
                            "ready" if payload["master"]["sha256"] == current_hash else "stale"
                        ),
                        "has_suggestions": payload["suggestions"] is not None,
                        "decision_counts": counts,
                        "stage": _session_stage(payload, counts),
                        "next_unresolved": _next_unresolved(payload),
                        "updated_at": payload["updated_at"],
                    }
                )
            except (KeyError, OSError, json.JSONDecodeError):
                continue
        return sorted(sessions, key=lambda item: item["updated_at"], reverse=True)

    def get_session(self, session_id: str) -> dict[str, Any]:
        _, payload = self._load(session_id)
        return _public_session(payload, self._current_hash())

    def archive_session(self, session_id: str) -> dict[str, str]:
        path, payload = self._load(session_id)
        destination = self.archive_directory / path.name
        self.archive_directory.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
            destination = self.archive_directory / f"{path.stem}-{timestamp}.json"
        os.replace(path, destination)
        return {"status": "archived", "session_id": payload["session_id"]}

    def reconcile_session(self, session_id: str) -> dict[str, Any]:
        path, payload = self._load(session_id)
        source = self.master_path.read_text(encoding="utf-8")
        payload["master"] = {"path": "master/_resume.tex", "sha256": _sha256(self.master_path)}
        payload["entries"] = _entry_records(source)
        payload["requirements"] = []
        payload["suggestions"] = None
        payload["confirmed_facts"] = []
        payload["revision_requests"] = []
        payload["history"] = []
        payload["preview"] = None
        payload["export"] = None
        payload["reconciled_at"] = _now()
        payload["updated_at"] = _now()
        _atomic_json(path, payload)
        return _public_session(payload, payload["master"]["sha256"])

    def suggestion_context(self, session_id: str) -> dict[str, Any]:
        _, payload = self._load(session_id)
        self._require_fresh(payload)
        entries = []
        for entry in payload["entries"]:
            entries.append(
                {
                    "entry_number": entry["entry_number"],
                    "section": entry["section"],
                    "title": entry["title"],
                    "subtitle": entry["subtitle"],
                    "date": entry["date"],
                    "is_project": entry["is_project"],
                    "bullets": [
                        {
                            "bullet_number": bullet["bullet_number"],
                            "text": bullet["source_text"],
                            "is_metadata": bullet["is_metadata"],
                        }
                        for bullet in entry["bullets"]
                    ],
                }
            )
        return {
            "session_id": payload["session_id"],
            "job": payload["job"],
            "entries": entries,
            "requirements": payload.get("requirements", []),
            "suggestions": payload.get("suggestions"),
            "revision_requests": payload.get("revision_requests", []),
            "instructions": {
                "bullet_actions": sorted(SUGGESTION_ACTIONS),
                "project_actions": sorted(PROJECT_ACTIONS),
                "rules": [
                    "Use only verified resume facts.",
                    "Do not change employer, title, school, or date fields.",
                    "Provide one suggestion for every bullet and one include/exclude suggestion for every project.",
                    "Each requirement must include an exact source_excerpt from the job description and use a supported category.",
                    "Every reason must be job-specific and concise.",
                    "A rewrite must contain complete replacement wording.",
                ],
            },
        }

    def save_analysis(
        self,
        session_id: str,
        *,
        requirements: list[dict[str, Any]],
        bullet_suggestions: list[dict[str, Any]],
        project_suggestions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        path, payload = self._load(session_id)
        current_hash = self._require_fresh(payload)
        normalized_requirements = self._normalize_requirements(
            requirements, payload["job"]["description"]
        )
        requirement_ids = {item["id"] for item in normalized_requirements}
        normalized_bullets = self._normalize_bullet_suggestions(
            payload, bullet_suggestions, requirement_ids
        )
        normalized_projects = self._normalize_project_suggestions(
            payload, project_suggestions, requirement_ids
        )
        for requirement in normalized_requirements:
            bullet_evidence = [
                {
                    "kind": "bullet",
                    "entry_number": item["entry_number"],
                    "bullet_number": item["bullet_number"],
                }
                for item in normalized_bullets
                if item["requirement_id"] == requirement["id"]
            ]
            project_evidence = [
                {"kind": "project", "entry_number": item["entry_number"]}
                for item in normalized_projects
                if item["requirement_id"] == requirement["id"] and item["action"] == "include"
            ]
            requirement["evidence"] = bullet_evidence + project_evidence
            requirement["supported"] = bool(requirement["evidence"])
            requirement["eligibility_mismatch"] = bool(
                requirement["category"] == "eligibility" and not requirement["supported"]
            )
        payload["requirements"] = normalized_requirements
        payload["suggestions"] = {
            "bullets": normalized_bullets,
            "projects": normalized_projects,
            "generated_at": _now(),
        }
        payload["preview"] = None
        payload["export"] = None
        payload["updated_at"] = _now()
        _atomic_json(path, payload)
        return _public_session(payload, current_hash)

    def request_revision(
        self,
        session_id: str,
        *,
        entry_number: int,
        bullet_number: int,
        instruction: str,
    ) -> dict[str, Any]:
        path, payload = self._load(session_id)
        current_hash = self._require_fresh(payload)
        instruction = instruction.strip()
        if not instruction:
            raise WorkspaceError("Describe the different suggestion you want.")
        entry = next(
            (item for item in payload["entries"] if item["entry_number"] == entry_number), None
        )
        if entry is None or not 1 <= bullet_number <= len(entry["bullets"]):
            raise WorkspaceError("The revision request points to an unknown bullet.")
        bullet = entry["bullets"][bullet_number - 1]
        before = copy.deepcopy(bullet["decision"])
        bullet["decision"] = None
        prior_suggestion = next(
            (
                item
                for item in (payload.get("suggestions") or {}).get("bullets", [])
                if item["entry_number"] == entry_number
                and item["bullet_number"] == bullet_number
            ),
            None,
        )
        if prior_suggestion is None:
            raise WorkspaceError("The original suggestion could not be found.")
        request_id = f"{entry_number}-{bullet_number}-{len(payload.get('revision_requests', [])) + 1}"
        payload.setdefault("revision_requests", []).append(
            {
                "id": request_id,
                "entry_number": entry_number,
                "bullet_number": bullet_number,
                "instruction": instruction,
                "status": "pending",
                "requested_at": _now(),
            }
        )
        payload["history"].append(
            {
                "saved_at": _now(),
                "bullets": [
                    {
                        "entry_number": entry_number,
                        "bullet_number": bullet_number,
                        "before": before,
                    }
                ],
                "projects": [],
                "facts": [],
                "revision_requests": [request_id],
                "suggestions": [
                    {
                        "entry_number": entry_number,
                        "bullet_number": bullet_number,
                        "before": copy.deepcopy(prior_suggestion),
                    }
                ],
            }
        )
        payload["preview"] = None
        payload["export"] = None
        payload["updated_at"] = _now()
        _atomic_json(path, payload)
        return _public_session(payload, current_hash)

    def save_revision(
        self,
        session_id: str,
        *,
        request_id: str,
        suggestion: dict[str, Any],
    ) -> dict[str, Any]:
        path, payload = self._load(session_id)
        current_hash = self._require_fresh(payload)
        request = next(
            (
                item
                for item in payload.get("revision_requests", [])
                if item["id"] == request_id and item["status"] == "pending"
            ),
            None,
        )
        if request is None:
            raise WorkspaceError("The pending revision request could not be found.")
        candidate = dict(suggestion)
        candidate["entry_number"] = request["entry_number"]
        candidate["bullet_number"] = request["bullet_number"]
        normalized = self._normalize_bullet_suggestions(
            {"entries": [
                {
                    **entry,
                    "bullets": (
                        [entry["bullets"][request["bullet_number"] - 1]]
                        if entry["entry_number"] == request["entry_number"]
                        else []
                    ),
                }
                for entry in payload["entries"]
                if entry["entry_number"] == request["entry_number"]
            ]},
            [candidate],
            {item["id"] for item in payload["requirements"]},
        )[0]
        suggestions = payload.get("suggestions")
        if suggestions is None:
            raise WorkspaceError("The original suggestion set is missing.")
        suggestions["bullets"] = [
            item
            for item in suggestions["bullets"]
            if not (
                item["entry_number"] == request["entry_number"]
                and item["bullet_number"] == request["bullet_number"]
            )
        ]
        suggestions["bullets"].append(normalized)
        suggestions["bullets"].sort(key=lambda item: (item["entry_number"], item["bullet_number"]))
        suggestions["generated_at"] = _now()
        request["status"] = "fulfilled"
        request["fulfilled_at"] = _now()
        payload["updated_at"] = _now()
        _atomic_json(path, payload)
        return _public_session(payload, current_hash)

    @staticmethod
    def _normalize_requirements(
        requirements: list[dict[str, Any]], job_description: str
    ) -> list[dict[str, Any]]:
        normalized = []
        seen: set[str] = set()
        normalized_description = " ".join(job_description.casefold().split())
        for index, requirement in enumerate(requirements, start=1):
            requirement_id = str(requirement.get("id") or f"requirement-{index}").strip()
            text = str(requirement.get("text") or "").strip()
            category = str(requirement.get("category") or "responsibility").strip()
            source_excerpt = str(requirement.get("source_excerpt") or "").strip()
            if not requirement_id or requirement_id in seen or not text:
                raise WorkspaceError("Every requirement needs a unique ID and non-empty text.")
            if category not in REQUIREMENT_CATEGORIES:
                raise WorkspaceError(f"Requirement {requirement_id} has an unsupported category.")
            if not source_excerpt:
                raise WorkspaceError(f"Requirement {requirement_id} needs a job-description excerpt.")
            if " ".join(source_excerpt.casefold().split()) not in normalized_description:
                raise WorkspaceError(
                    f"Requirement {requirement_id} has an excerpt that is not in the job description."
                )
            seen.add(requirement_id)
            normalized.append(
                {
                    "id": requirement_id,
                    "text": text,
                    "category": category,
                    "source_excerpt": source_excerpt,
                }
            )
        if not normalized:
            raise WorkspaceError("The analysis must include at least one job requirement.")
        return normalized

    @staticmethod
    def _normalize_bullet_suggestions(
        payload: dict[str, Any],
        suggestions: list[dict[str, Any]],
        requirement_ids: set[str],
    ) -> list[dict[str, Any]]:
        entries = {entry["entry_number"]: entry for entry in payload["entries"]}
        expected = {
            (entry["entry_number"], bullet["bullet_number"])
            for entry in payload["entries"]
            for bullet in entry["bullets"]
        }
        normalized = []
        seen: set[tuple[int, int]] = set()
        for suggestion in suggestions:
            entry_number = int(suggestion["entry_number"])
            bullet_number = int(suggestion["bullet_number"])
            key = (entry_number, bullet_number)
            entry = entries.get(entry_number)
            if entry is None or key not in expected or key in seen:
                raise WorkspaceError(f"Invalid or duplicate bullet suggestion {entry_number}.{bullet_number}.")
            action = str(suggestion.get("action") or "").casefold()
            if action not in SUGGESTION_ACTIONS:
                raise WorkspaceError(f"Unsupported suggestion action: {action}.")
            suggested_text = str(suggestion.get("suggested_text") or "").strip()
            if action == "rewrite" and not suggested_text:
                raise WorkspaceError(f"Rewrite {entry_number}.{bullet_number} needs replacement text.")
            reason = str(suggestion.get("reason") or "").strip()
            if not reason:
                raise WorkspaceError(f"Suggestion {entry_number}.{bullet_number} needs a reason.")
            requirement_id = str(suggestion.get("requirement_id") or "").strip() or None
            if requirement_id and requirement_id not in requirement_ids:
                raise WorkspaceError(f"Suggestion {entry_number}.{bullet_number} has an unknown requirement.")
            seen.add(key)
            normalized.append(
                {
                    "entry_number": entry_number,
                    "bullet_number": bullet_number,
                    "action": action,
                    "suggested_text": suggested_text or None,
                    "reason": reason,
                    "requirement_id": requirement_id,
                }
            )
        missing = sorted(expected - seen)
        if missing:
            label = ", ".join(f"{entry}.{bullet}" for entry, bullet in missing)
            raise WorkspaceError(f"The complete suggestion set is missing: {label}.")
        return normalized

    @staticmethod
    def _normalize_project_suggestions(
        payload: dict[str, Any],
        suggestions: list[dict[str, Any]],
        requirement_ids: set[str],
    ) -> list[dict[str, Any]]:
        expected = {
            entry["entry_number"] for entry in payload["entries"] if entry["is_project"]
        }
        normalized = []
        seen: set[int] = set()
        for suggestion in suggestions:
            entry_number = int(suggestion["entry_number"])
            if entry_number not in expected or entry_number in seen:
                raise WorkspaceError(f"Invalid or duplicate project suggestion {entry_number}.")
            action = str(suggestion.get("action") or "").casefold()
            if action not in PROJECT_ACTIONS:
                raise WorkspaceError(f"Unsupported project suggestion action: {action}.")
            reason = str(suggestion.get("reason") or "").strip()
            if not reason:
                raise WorkspaceError(f"Project suggestion {entry_number} needs a reason.")
            requirement_id = str(suggestion.get("requirement_id") or "").strip() or None
            if requirement_id and requirement_id not in requirement_ids:
                raise WorkspaceError(f"Project suggestion {entry_number} has an unknown requirement.")
            seen.add(entry_number)
            normalized.append(
                {
                    "entry_number": entry_number,
                    "action": action,
                    "reason": reason,
                    "requirement_id": requirement_id,
                }
            )
        if seen != expected:
            missing = ", ".join(str(item) for item in sorted(expected - seen))
            raise WorkspaceError(f"The complete analysis is missing project suggestions: {missing}.")
        return normalized

    def apply_decisions(
        self,
        session_id: str,
        *,
        bullet_decisions: list[dict[str, Any]] | None = None,
        project_decisions: list[dict[str, Any]] | None = None,
        confirmed_facts: list[str] | None = None,
    ) -> dict[str, Any]:
        path, payload = self._load(session_id)
        current_hash = self._require_fresh(payload)
        if payload["suggestions"] is None:
            raise WorkspaceError("Suggestions must be prepared before decisions can be saved.")
        entries = {entry["entry_number"]: entry for entry in payload["entries"]}
        history = {
            "saved_at": _now(),
            "bullets": [],
            "projects": [],
            "facts": [],
            "revision_requests": [],
            "suggestions": [],
        }

        for requested in bullet_decisions or []:
            entry_number = int(requested["entry_number"])
            bullet_number = int(requested["bullet_number"])
            entry = entries.get(entry_number)
            if entry is None or not 1 <= bullet_number <= len(entry["bullets"]):
                raise WorkspaceError("A decision points to an unknown resume bullet.")
            action = str(requested.get("action") or "").casefold()
            if action not in DECISION_ACTIONS:
                raise WorkspaceError(f"Unsupported bullet decision: {action}.")
            accepted_text = str(requested.get("accepted_text") or "").strip()
            if action == "rewrite" and not accepted_text:
                raise WorkspaceError("A rewrite decision requires accepted wording.")
            bullet = entry["bullets"][bullet_number - 1]
            before = copy.deepcopy(bullet["decision"])
            if action == "keep":
                after = {"action": "keep", "accepted_text": bullet["source_text"], "decided_at": _now()}
            elif action == "remove":
                after = {"action": "remove", "accepted_text": None, "decided_at": _now()}
            else:
                after = {"action": "rewrite", "accepted_text": accepted_text, "decided_at": _now()}
            bullet["decision"] = after
            history["bullets"].append(
                {"entry_number": entry_number, "bullet_number": bullet_number, "before": before}
            )

        for requested in project_decisions or []:
            entry_number = int(requested["entry_number"])
            entry = entries.get(entry_number)
            if entry is None or not entry["is_project"]:
                raise WorkspaceError("A project decision points to a non-project entry.")
            action = str(requested.get("action") or "").casefold()
            if action not in PROJECT_ACTIONS:
                raise WorkspaceError(f"Unsupported project decision: {action}.")
            before = copy.deepcopy(entry["project_decision"])
            entry["project_decision"] = {"action": action, "decided_at": _now()}
            history["projects"].append({"entry_number": entry_number, "before": before})

        for fact in confirmed_facts or []:
            fact = str(fact).strip()
            if fact and fact not in payload["confirmed_facts"]:
                payload["confirmed_facts"].append(fact)
                history["facts"].append(fact)

        if not history["bullets"] and not history["projects"] and not history["facts"]:
            raise WorkspaceError("No decisions were provided.")
        payload["history"].append(history)
        payload["preview"] = None
        payload["export"] = None
        payload["updated_at"] = _now()
        _atomic_json(path, payload)
        return _public_session(payload, current_hash)

    def undo(self, session_id: str) -> dict[str, Any]:
        path, payload = self._load(session_id)
        current_hash = self._require_fresh(payload)
        if not payload["history"]:
            raise WorkspaceError("There is no decision to undo.")
        batch = payload["history"].pop()
        entries = {entry["entry_number"]: entry for entry in payload["entries"]}
        for change in reversed(batch["bullets"]):
            entries[change["entry_number"]]["bullets"][change["bullet_number"] - 1][
                "decision"
            ] = change["before"]
        for change in reversed(batch["projects"]):
            entries[change["entry_number"]]["project_decision"] = change["before"]
        for fact in batch["facts"]:
            if fact in payload["confirmed_facts"]:
                payload["confirmed_facts"].remove(fact)
        request_ids = set(batch.get("revision_requests", []))
        if request_ids:
            payload["revision_requests"] = [
                item
                for item in payload.get("revision_requests", [])
                if item["id"] not in request_ids
            ]
        suggestions = payload.get("suggestions")
        if suggestions:
            for change in batch.get("suggestions", []):
                suggestions["bullets"] = [
                    item
                    for item in suggestions["bullets"]
                    if not (
                        item["entry_number"] == change["entry_number"]
                        and item["bullet_number"] == change["bullet_number"]
                    )
                ]
                suggestions["bullets"].append(change["before"])
            suggestions["bullets"].sort(
                key=lambda item: (item["entry_number"], item["bullet_number"])
            )
        payload["preview"] = None
        payload["export"] = None
        payload["updated_at"] = _now()
        _atomic_json(path, payload)
        return _public_session(payload, current_hash)

    @staticmethod
    def _latex_text(value: str) -> str:
        replacements = {
            "\\": r"\textbackslash{}",
            "&": r"\&",
            "%": r"\%",
            "$": r"\$",
            "#": r"\#",
            "_": r"\_",
            "{": r"\{",
            "}": r"\}",
            "~": r"\textasciitilde{}",
            "^": r"\textasciicircum{}",
        }
        escaped = "".join(replacements.get(character, character) for character in value)
        metadata = re.match(r"^(Technologies|Technology|Tools|GPA|Relevant Coursework):\s*(.*)$", value)
        if metadata:
            label = metadata.group(1)
            remainder = "".join(replacements.get(character, character) for character in metadata.group(2))
            escaped = rf"{{\bfseries {label}:}} {remainder}"
        return escaped

    @staticmethod
    def _entry_locations(source: str) -> list[dict[str, Any]]:
        locations = []
        cursor = 0
        while True:
            command_start = source.find("\\customcventry", cursor)
            if command_start < 0:
                return locations
            try:
                arguments = _entry_arguments(source, command_start)
            except ResumeValidationError:
                cursor = command_start + len("\\customcventry")
                continue
            content_start, content_end = arguments[3]
            content = source[content_start:content_end]
            begin = content.find("\\begin{itemize}")
            end = content.rfind("\\end{itemize}")
            bullet_locations = []
            if begin >= 0 and end > begin:
                region_start = content_start + begin + len("\\begin{itemize}")
                region = source[region_start : content_start + end]
                matches = list(ITEM_RE.finditer(region))
                for index, match in enumerate(matches):
                    next_start = matches[index + 1].start() if index + 1 < len(matches) else len(region)
                    bullet_locations.append(
                        {
                            "item_start": region_start + match.start(),
                            "body_start": region_start + match.end(),
                            "item_end": region_start + next_start,
                        }
                    )
            locations.append(
                {
                    "command_start": command_start,
                    "command_end": arguments[3][1] + 1,
                    "bullets": bullet_locations,
                }
            )
            cursor = arguments[3][1] + 1

    def assemble_source(self, session_id: str, *, require_complete: bool) -> str:
        _, payload = self._load(session_id)
        self._require_fresh(payload)
        source = self.master_path.read_text(encoding="utf-8")
        locations = self._entry_locations(source)
        if len(locations) != len(payload["entries"]):
            raise WorkspaceError("The master resume structure no longer matches the session.")
        edits: list[tuple[int, int, str]] = []
        for entry, location in zip(payload["entries"], locations, strict=True):
            if entry["is_project"]:
                project_decision = entry["project_decision"]
                if project_decision is None:
                    if require_complete:
                        raise WorkspaceError(f"Choose whether to include {entry['title']} before export.")
                elif project_decision["action"] == "exclude":
                    edits.append((location["command_start"], location["command_end"], ""))
                    continue
            for bullet, bullet_location in zip(entry["bullets"], location["bullets"], strict=True):
                decision = bullet["decision"]
                if decision is None:
                    if require_complete and (
                        not entry["is_project"]
                        or (entry.get("project_decision") or {}).get("action") == "include"
                    ):
                        raise WorkspaceError(
                            f"Decide {entry['title']} bullet {bullet['bullet_number']} before export."
                        )
                    continue
                if decision["action"] == "keep":
                    continue
                if decision["action"] == "remove":
                    edits.append((bullet_location["item_start"], bullet_location["item_end"], ""))
                else:
                    replacement = " " + self._latex_text(decision["accepted_text"]) + "\n"
                    edits.append(
                        (bullet_location["body_start"], bullet_location["item_end"], replacement)
                    )
        for start, end, replacement in sorted(edits, reverse=True):
            source = source[:start] + replacement + source[end:]
        source = re.sub(r"(?m)^[ \t]*\\newpage[ \t]*(?:\n|$)", "", source)
        project_entries = [entry for entry in payload["entries"] if entry["is_project"]]
        if project_entries and all(
            (entry.get("project_decision") or {}).get("action") == "exclude"
            for entry in project_entries
        ):
            source = re.sub(r"(?m)^[ \t]*\\section\{Projects\}[ \t]*(?:\n|$)", "", source)
        errors = validate_tailored_tex(
            self.master_path.read_text(encoding="utf-8"),
            source,
            payload["confirmed_facts"],
        )
        errors.extend(
            validate_tailored_completeness(
                self.master_path.read_text(encoding="utf-8"), source
            )
        )
        if errors:
            raise WorkspaceError(" ".join(errors))
        return source

    def _build_at(self, relative_folder: str) -> dict[str, Any]:
        command = [str(self.repository / "scripts" / "build_resume.sh"), relative_folder]
        result = subprocess.run(
            command,
            cwd=self.repository,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip().splitlines()
            raise WorkspaceError(detail[-1] if detail else "The PDF build failed.")
        pdf_path = self.repository / relative_folder / "Morgan_Le_Resume.pdf"
        report = verify_pdf(pdf_path)
        return {
            "pages": report.pages,
            "a4": report.a4,
            "links": report.links,
            "extracted_characters": report.extracted_characters,
        }

    def build_preview(self, session_id: str) -> dict[str, Any]:
        path, payload = self._load(session_id)
        self._require_fresh(payload)
        source = self.assemble_source(session_id, require_complete=False)
        preview_folder = self.previews_directory / session_id
        relative_folder = str(preview_folder.relative_to(self.repository))
        _atomic_text(preview_folder / "_resume.tex", source)
        report = self._build_at(relative_folder)
        payload["preview"] = {
            "report": report,
            "built_at": _now(),
            "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "url": f"/api/sessions/{session_id}/preview.pdf",
            "page_fit_opportunities": self.page_fit_opportunities(payload) if report["pages"] > 1 else [],
        }
        payload["updated_at"] = _now()
        _atomic_json(path, payload)
        return {"status": "ready", **payload["preview"]}

    def preview_path(self, session_id: str) -> Path:
        self._path(session_id)
        return self.previews_directory / session_id / "Morgan_Le_Resume.pdf"

    @staticmethod
    def page_fit_opportunities(payload: dict[str, Any]) -> list[dict[str, Any]]:
        suggestion_map = {
            (item["entry_number"], item["bullet_number"]): item
            for item in (payload.get("suggestions") or {}).get("bullets", [])
        }
        candidates = []
        for entry in payload["entries"]:
            if entry["is_project"] and (entry.get("project_decision") or {}).get("action") != "include":
                continue
            for bullet in entry["bullets"]:
                if (bullet.get("decision") or {}).get("action") == "remove":
                    continue
                suggestion = suggestion_map.get((entry["entry_number"], bullet["bullet_number"]), {})
                priority = 0 if bullet["is_metadata"] else 1 if suggestion.get("action") == "remove" else 2
                candidates.append(
                    {
                        "entry_number": entry["entry_number"],
                        "bullet_number": bullet["bullet_number"],
                        "entry_title": entry["title"],
                        "text": bullet["source_text"],
                        "reason": (
                            "Consolidate this tools list into the skills section."
                            if bullet["is_metadata"]
                            else suggestion.get("reason") or "Consider a shorter rewrite or removal."
                        ),
                        "priority": priority,
                    }
                )
        return sorted(candidates, key=lambda item: (item["priority"], item["entry_number"], item["bullet_number"]))[:8]

    def export(self, session_id: str, *, overwrite: bool = False) -> dict[str, Any]:
        path, payload = self._load(session_id)
        self._require_fresh(payload)
        source = self.assemble_source(session_id, require_complete=True)
        source_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()
        preview = payload.get("preview")
        if (
            not preview
            or preview.get("source_sha256") != source_hash
            or preview.get("report", {}).get("pages") != 1
        ):
            raise WorkspaceError("Build and review a current one-page preview before export.")
        target = (self.repository / payload["target_slug"]).resolve()
        if self.repository not in target.parents or target.parent != self.repository:
            raise WorkspaceError("The export folder must be directly inside the repository.")
        if target.exists() and any(target.iterdir()) and not overwrite:
            raise WorkspaceError("That tailored folder already exists. Confirm overwrite to continue.")
        unrelated = (
            [
                item.name
                for item in target.iterdir()
                if item.name not in {"_resume.tex", "Morgan_Le_Resume.pdf"}
            ]
            if target.exists()
            else []
        )
        if unrelated:
            raise WorkspaceError("The target folder contains unrelated files and cannot be overwritten.")
        with tempfile.TemporaryDirectory(prefix=".resume-export-", dir=self.repository) as staging_name:
            staging = Path(staging_name)
            _atomic_text(staging / "_resume.tex", source)
            report = self._build_at(str(staging.relative_to(self.repository)))
            if report["pages"] != 1:
                raise WorkspaceError(
                    f"The tailored resume is {report['pages']} pages. Approve additional fitting choices before export."
                )
            pdf_bytes = (staging / "Morgan_Le_Resume.pdf").read_bytes()
        target.mkdir(parents=True, exist_ok=True)
        _atomic_text(target / "_resume.tex", source)
        _atomic_bytes(target / "Morgan_Le_Resume.pdf", pdf_bytes)
        payload["export"] = {
            "report": report,
            "exported_at": _now(),
            "source": str((target / "_resume.tex").relative_to(self.repository)),
            "pdf": str((target / "Morgan_Le_Resume.pdf").relative_to(self.repository)),
        }
        payload["updated_at"] = _now()
        _atomic_json(path, payload)
        return {"status": "ready", **payload["export"]}
