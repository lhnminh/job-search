from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from openai_codex import ApprovalMode, Codex, LocalImageInput, Sandbox, TextInput, Thread
from openai_codex.api import ReasoningEffort


BASE_INSTRUCTIONS = """Role: You are a conversational resume editor working inside this resume repository.

Goal: Help the user create accurate, relevant, concise resume variants and review existing content.

Constraints:
- Read AGENTS.md and SPEC.md before responding.
- Do not modify files or run write commands. The Python controller applies accepted changes.
- Treat the root _resume.tex as the verified factual reference.
- Never invent employers, historical titles, dates, metrics, technologies, responsibilities, or outcomes.
- You may ask for a missing fact. Treat it as verified only after the user explicitly confirms it.
- Preserve historical employer names and titles exactly.
- Return LaTeX-ready text when a schema requests LaTeX.
- Tailored resumes must fit exactly one A4 page. Preserve every verified work position with at least one substantive bullet, prioritize additional bullets for the most relevant roles, and compress repetition before removing a role.

Collaboration: Be direct and specific. Explain the evidence behind recommendations. Accept natural-language revision instructions.

Stop rule: If a requested claim is not supported by the root source or explicit user input, ask for confirmation instead of guessing.
"""


class CodexBackendError(RuntimeError):
    pass


def authentication_status() -> tuple[bool, str]:
    process = subprocess.run(["codex", "login", "status"], text=True, capture_output=True)
    output = "\n".join(part for part in (process.stdout, process.stderr) if part).strip()
    return process.returncode == 0 and "logged in" in output.casefold(), output


class CodexConversation:
    def __init__(self, repo_root: Path, thread_id: str | None = None):
        self.repo_root = repo_root
        self.thread_id = thread_id
        self._codex: Codex | None = None
        self.thread: Thread | None = None

    def __enter__(self) -> "CodexConversation":
        self._codex = Codex()
        self._codex.__enter__()
        common = {
            "cwd": str(self.repo_root),
            "sandbox": Sandbox.read_only,
            "approval_mode": ApprovalMode.deny_all,
            "developer_instructions": BASE_INSTRUCTIONS,
        }
        if self.thread_id:
            self.thread = self._codex.thread_resume(self.thread_id, **common)
        else:
            self.thread = self._codex.thread_start(**common)
            self.thread_id = self.thread.id
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._codex is not None:
            self._codex.__exit__(exc_type, exc, traceback)

    def run_text(self, prompt: str) -> str:
        if self.thread is None:
            raise CodexBackendError("Codex conversation is not open")
        result = self.thread.run(
            prompt,
            sandbox=Sandbox.read_only,
            approval_mode=ApprovalMode.deny_all,
            effort=ReasoningEffort.low,
        )
        if result.error:
            raise CodexBackendError(str(result.error))
        if not result.final_response:
            raise CodexBackendError("Codex returned no final response")
        return result.final_response.strip()

    def run_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        return self._run_json_input(prompt, schema)

    def run_json_with_images(
        self,
        prompt: str,
        image_paths: list[Path],
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        input_items = [TextInput(prompt), *(LocalImageInput(str(path)) for path in image_paths)]
        return self._run_json_input(input_items, schema)

    def _run_json_input(self, prompt: Any, schema: dict[str, Any]) -> dict[str, Any]:
        if self.thread is None:
            raise CodexBackendError("Codex conversation is not open")
        result = self.thread.run(
            prompt,
            sandbox=Sandbox.read_only,
            approval_mode=ApprovalMode.deny_all,
            effort=ReasoningEffort.low,
            output_schema=schema,
        )
        if result.error:
            raise CodexBackendError(str(result.error))
        if not result.final_response:
            raise CodexBackendError("Codex returned no final response")
        payload = result.final_response.strip()
        fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", payload, flags=re.DOTALL)
        if fenced:
            payload = fenced.group(1)
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise CodexBackendError(f"Codex returned invalid structured output: {exc}") from exc
        if not isinstance(value, dict):
            raise CodexBackendError("Codex structured output was not an object")
        return value
