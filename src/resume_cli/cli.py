from __future__ import annotations

import difflib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .build import BuildError, BuildResult, PdfRenderError, PdfReport, build_resume, render_pdf
from .codex_backend import CodexBackendError, CodexConversation, authentication_status
from .resume import (
    ResumeDocument,
    apply_line_decisions,
    append_bullet,
    append_bullet_by_title,
    parse_resume,
    prepare_interactive_tailored_source,
    remove_bullet,
    replace_bullet,
    resume_path,
    slugify,
    source_hash,
    tex_to_text,
    validate_root_append_only,
    validate_slug,
    validate_tailored_completeness,
    validate_tailored_tex,
)
from .schemas import (
    BULLET_REVIEW_SCHEMA,
    FACT_AUDIT_SCHEMA,
    LINE_REVIEW_BATCH_SCHEMA,
    LINE_REVIEW_SCHEMA,
    SECTION_REVIEW_SCHEMA,
    TAILOR_SCHEMA,
    VISUAL_QA_SCHEMA,
)
from .session import Session, SessionStore


app = typer.Typer(
    add_completion=False,
    no_args_is_help=False,
    help="Chat with Codex to tailor and review resume versions.",
)
console = Console()
REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_multiline(label: str, *, optional: bool = False) -> str:
    console.print(label)
    console.print("[dim]Paste text, then enter a line containing only .done[/dim]")
    lines: list[str] = []
    while True:
        try:
            line = console.input("[cyan]> [/cyan]")
        except EOFError:
            break
        if line.strip() == ".done":
            break
        lines.append(line)
    value = "\n".join(lines).strip()
    if not value and not optional:
        raise typer.BadParameter("Text cannot be empty")
    return value


def _require_authentication() -> None:
    authenticated, output = authentication_status()
    if not authenticated:
        console.print(Panel(output or "Codex is not authenticated.", title="Authentication required", style="red"))
        console.print("Run [bold]codex login[/bold], then retry.")
        raise typer.Exit(2)


def _show_tailor_proposal(proposal: dict[str, Any]) -> None:
    console.print(Panel("\n".join(f"• {item}" for item in proposal["summary"]), title="Codex recommendation"))
    console.print(f"Suggested folder: [bold cyan]{proposal['suggested_slug']}[/bold cyan]")
    questions = proposal.get("questions") or []
    if questions:
        console.print("[yellow]Codex needs confirmation:[/yellow]")
        for question in questions:
            console.print(f"  • {question}")


def _show_diff(before: str, after: str, *, limit: int = 240) -> None:
    lines = list(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile="before/_resume.tex",
            tofile="after/_resume.tex",
            lineterm="",
        )
    )
    if not lines:
        console.print("[dim]No LaTeX changes.[/dim]")
        return
    truncated = len(lines) > limit
    rendered = lines[:limit]
    if truncated:
        rendered.append(f"... diff truncated ({len(lines) - limit} additional lines)")
    text = Text()
    for line in rendered:
        style = "green" if line.startswith("+") and not line.startswith("+++") else None
        if line.startswith("-") and not line.startswith("---"):
            style = "red"
        elif line.startswith("@@"):
            style = "cyan"
        text.append(line + "\n", style=style)
    console.print(Panel(text, title="Proposed changes"))


def _tailor_prompt(job_description: str) -> str:
    return f"""Create a complete application-specific resume from the root _resume.tex.

Job description:
<job_description>
{job_description}
</job_description>

Success criteria:
- Return a full compilable _resume.tex using the existing document style and contact details.
- Preserve the root \\firstname, \\familyname, \\mobile, \\email, \\github, and \\linkedin lines verbatim.
- Select and rewrite only facts verified in root _resume.tex.
- Preserve all historical employer names, job titles, dates, and numeric facts.
- Produce a polished resume of exactly one A4 page.
- Preserve every verified work position from the root source.
- Keep at least one substantive achievement bullet per position; technology bullets do not count toward this minimum.
- Prioritize additional bullets for the positions most relevant to the job description.
- Consolidate repeated technology lists into the skills section before removing substantive experience.
- Select and condense projects as needed after every work position is represented.
- Do not use \\newpage.
- Suggest a lowercase hyphenated folder slug based on company, role, or discipline.
- Put any factual questions requiring user confirmation in questions. Do not use those facts in source_tex yet.
- Return only the required structured output.
"""


def _revision_prompt(instruction: str) -> str:
    return f"""Revise your most recent tailored resume proposal using this user instruction:

<user_instruction>
{instruction}
</user_instruction>

Return the complete revised _resume.tex and the other required structured fields. Preserve verified facts and the one-page requirement.
"""


def _fit_prompt(current_tex: str, build_issue: str) -> str:
    return f"""Revise this tailored resume so it compiles and fits exactly one A4 page.

Build result:
{build_issue}

Current LaTeX:
<current_tex>
{current_tex}
</current_tex>

Preserve historical titles and verified facts. Preserve every work position with at least one substantive bullet, and prioritize additional bullets for the most relevant roles. Consolidate repeated technologies and tighten wording before removing substantive content. Preserve the existing \\firstname, \\familyname, \\mobile, \\email, \\github, and \\linkedin lines verbatim. Preserve legibility and the overall style. Return the full revised LaTeX in source_tex and the required structured fields.
"""


def _confirmed_facts(session: Session) -> list[str]:
    return list(session.payload.get("confirmed_facts", []))


def _validate_proposal(root_source: str, proposal: dict[str, Any], session: Session) -> list[str]:
    source_tex = proposal.get("source_tex")
    if not isinstance(source_tex, str) or not source_tex.strip():
        return ["Codex did not return LaTeX source"]
    return [
        *validate_tailored_tex(root_source, source_tex, _confirmed_facts(session)),
        *validate_tailored_completeness(root_source, source_tex),
    ]


def _visual_pdf_qa(chat: CodexConversation, report: PdfReport) -> dict[str, Any]:
    qa_parent = REPO_ROOT / "tmp" / "pdfs"
    qa_parent.mkdir(parents=True, exist_ok=True)
    qa_directory = Path(tempfile.mkdtemp(prefix="resume-cli-", dir=qa_parent))
    try:
        images = render_pdf(report.path, qa_directory)
        if len(images) != report.pages:
            raise PdfRenderError(
                f"Rendered {len(images)} QA image(s) for a {report.pages}-page PDF; visual verification is incomplete"
            )
        prompt = f"""Inspect every attached page of {report.path.name} as a final resume PDF.

Approve only when all pages are professionally readable and contain no clipped text, overlapping text, broken or missing glyphs, awkward page breaks, orphaned headings, or content extending beyond page boundaries. Normal intentional whitespace is acceptable. Report exact page numbers for issues. This is visual layout QA only; do not rewrite content or modify files.
"""
        with console.status("Codex is visually inspecting the final PDF..."):
            result = chat.run_json_with_images(prompt, images, VISUAL_QA_SCHEMA)
        if not result["approved"]:
            details = "; ".join(
                f"page {issue['page']} {issue['severity']}: {issue['description']}"
                for issue in result["issues"]
            )
            raise BuildError(f"Visual PDF verification failed: {details or result['summary']}")
        return result
    finally:
        shutil.rmtree(qa_directory, ignore_errors=True)
        for directory in (qa_parent, qa_parent.parent):
            try:
                directory.rmdir()
            except OSError:
                pass


def _factual_audit(chat: CodexConversation, source_tex: str, confirmed_facts: list[str]) -> list[str]:
    confirmations = "\n".join(f"- {fact}" for fact in confirmed_facts) or "- None"
    prompt = f"""Audit every factual claim in this proposed tailored resume against root _resume.tex and the explicit user confirmations below.

Explicit user confirmations:
{confirmations}

Proposed LaTeX:
<proposed_resume>
{source_tex}
</proposed_resume>

Rewriting, condensing, combining, and reordering verified root facts is allowed. A claim is unsupported if it introduces or materially strengthens an employer, title, date, responsibility, technology, metric, scope, or outcome that is absent from both the root source and the explicit confirmations. Ignore stylistic differences. Approve only when no unsupported claim remains. Do not modify files.
"""
    with console.status("Codex is auditing factual support..."):
        audit = chat.run_json(prompt, FACT_AUDIT_SCHEMA)
    if audit["approved"]:
        return []
    return [
        f"Unsupported claim: {issue['claim']} ({issue['reason']})"
        for issue in audit["unsupported_claims"]
    ] or [audit["summary"]]


def _unique_slug(candidate: str) -> str:
    base = slugify(candidate) or "tailored-resume"
    slug = base
    index = 2
    while (REPO_ROOT / slug).exists():
        slug = f"{base}-{index}"
        index += 1
    return slug


def _choose_slug(proposal: dict[str, Any], requested: str | None, assume_yes: bool) -> tuple[str, bool]:
    candidate = slugify(requested or proposal["suggested_slug"])
    errors = validate_slug(candidate)
    if errors:
        raise typer.BadParameter("; ".join(errors))
    if not assume_yes:
        entered = console.input(f"Folder slug [[bold]{candidate}[/bold]]: ").strip()
        if entered:
            candidate = slugify(entered)
            errors = validate_slug(candidate)
            if errors:
                raise typer.BadParameter("; ".join(errors))
    folder = REPO_ROOT / candidate
    overwrite = False
    if folder.exists():
        if assume_yes:
            candidate = _unique_slug(candidate)
            console.print(f"Existing folder preserved; using [bold]{candidate}[/bold].")
        else:
            overwrite = typer.confirm(f"{candidate}/ already exists. Replace its _resume.tex and PDF?", default=False)
            if not overwrite:
                entered = console.input("New folder slug: ").strip()
                candidate = slugify(entered)
                errors = validate_slug(candidate)
                if errors:
                    raise typer.BadParameter("; ".join(errors))
                if (REPO_ROOT / candidate).exists():
                    raise typer.BadParameter(f"Folder already exists: {candidate}")
    return candidate, overwrite


def _build_tailored_until_one_page(
    *,
    chat: CodexConversation,
    session: Session,
    root_source: str,
    target: str,
    confirm_revisions: bool,
    max_attempts: int = 4,
) -> BuildResult:
    source_path = resume_path(REPO_ROOT, target)
    last_issue = ""
    for attempt in range(1, max_attempts + 1):
        try:
            result = build_resume(REPO_ROOT, target)
            if result.report.pages == 1:
                try:
                    _visual_pdf_qa(chat, result.report)
                except PdfRenderError:
                    raise
                except BuildError as exc:
                    last_issue = str(exc)
                else:
                    return result
            else:
                last_issue = f"The generated PDF has {result.report.pages} pages; it must have exactly one."
        except PdfRenderError:
            raise
        except BuildError as exc:
            last_issue = f"Tectonic or PDF verification failed:\n{exc}"
        if attempt == max_attempts:
            break
        console.print(f"[yellow]{last_issue}[/yellow]")
        with console.status("Codex is tightening the resume..."):
            proposal = chat.run_json(_fit_prompt(session.working_tex, last_issue), TAILOR_SCHEMA)
        errors = _validate_proposal(root_source, proposal, session)
        if errors:
            last_issue = "Codex revision failed validation: " + "; ".join(errors)
            continue
        revised = proposal["source_tex"]
        audit_errors = _factual_audit(chat, revised, _confirmed_facts(session))
        if audit_errors:
            last_issue = "Codex revision failed factual audit: " + "; ".join(audit_errors)
            continue
        if confirm_revisions:
            _show_diff(session.working_tex, revised)
            if not typer.confirm("Use this page-fit revision?", default=True):
                raise BuildError("Page-fit revision was declined")
        session.history.append(session.working_tex)
        session.working_tex = revised
        session.payload["proposal"] = proposal
        SessionStore(REPO_ROOT).save(session)
        source_path.write_text(revised, encoding="utf-8")
    raise BuildError(last_issue or "Could not produce a one-page tailored PDF")


def _answer_proposal_questions(
    chat: CodexConversation,
    proposal: dict[str, Any],
    session: Session,
    assume_yes: bool,
) -> dict[str, Any]:
    current = proposal
    asked: set[str] = set()
    for _ in range(3):
        questions = [question for question in current.get("questions") or [] if question not in asked]
        if not questions:
            return current
        if assume_yes:
            raise typer.BadParameter("Codex needs factual confirmation; rerun without --yes")
        answers: list[str] = []
        for question in questions:
            asked.add(question)
            answer = console.input(f"[yellow]{question}[/yellow]\nYou: ").strip()
            if answer:
                answers.append(f"Question: {question}\nUser answer: {answer}")
                session.payload.setdefault("confirmed_facts", []).append(answer)
        if not answers:
            with console.status("Codex is removing unconfirmed material..."):
                current = chat.run_json(
                    "The user did not confirm the factual questions. Revise the proposal without those facts and return no repeated questions.",
                    TAILOR_SCHEMA,
                )
        else:
            with console.status("Codex is incorporating the confirmed facts..."):
                current = chat.run_json(
                    "The user supplied these factual answers. Treat only these explicit answers as newly verified and revise the full proposal:\n\n"
                    + "\n\n".join(answers),
                    TAILOR_SCHEMA,
                )
    return current


def _complete_tailor_build(
    session: Session,
    chat: CodexConversation,
    root_source: str,
    *,
    assume_yes: bool,
) -> None:
    store = SessionStore(REPO_ROOT)
    target = session.target
    folder = REPO_ROOT / target
    folder.mkdir(parents=False, exist_ok=True)
    source_path = folder / "_resume.tex"
    previous = session.payload.get("original_tex", "")
    source_path.write_text(session.working_tex, encoding="utf-8")
    try:
        result = _build_tailored_until_one_page(
            chat=chat,
            session=session,
            root_source=root_source,
            target=target,
            confirm_revisions=not assume_yes,
        )
    except Exception:
        if previous:
            source_path.write_text(previous, encoding="utf-8")
            try:
                build_resume(REPO_ROOT, target)
            except BuildError:
                pass
        else:
            source_path.unlink(missing_ok=True)
            (folder / "Morgan_Le_Resume.pdf").unlink(missing_ok=True)
            try:
                folder.rmdir()
            except OSError:
                pass
        session.payload["phase"] = "building"
        store.save(session)
        raise
    session.complete = True
    session.payload["phase"] = "complete"
    store.save(session)
    console.print(
        Panel(
            f"Created [bold]{target}/Morgan_Le_Resume.pdf[/bold]\n"
            f"Pages: {result.report.pages} | A4: yes | Links: {result.report.links} | "
            f"Text characters: {sum(result.report.extracted_characters)}",
            title="Tailored resume ready",
            style="green",
        )
    )


def _line_records(source: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for entry in parse_resume(source).entries:
        for bullet in entry.bullets:
            records.append(
                {
                    "id": bullet.id,
                    "entry_id": entry.id,
                    "section": bullet.section,
                    "entry_title": bullet.entry_title,
                    "entry_subtitle": bullet.entry_subtitle,
                    "date": entry.date,
                    "text": bullet.text,
                    "is_metadata": bullet.is_metadata,
                }
            )
    return records


def _entry_groups(source: str) -> list[dict[str, Any]]:
    return [
        {
            "id": entry.id,
            "section": entry.section,
            "title": entry.title,
            "subtitle": entry.subtitle,
            "date": entry.date,
            "line_ids": [bullet.id for bullet in entry.bullets],
        }
        for entry in parse_resume(source).entries
        if entry.bullets
    ]


def _batch_line_review_prompt(records: list[dict[str, Any]], job_description: str) -> str:
    lines = "\n".join(
        f"{record['id']} | {record['section']} | {record['entry_title']} | "
        f"{record['entry_subtitle']} | {record['date']} | {record['text']}"
        for record in records
    )
    return f"""Review every listed resume content line for this job in one batch.

Job description:
<job_description>
{job_description}
</job_description>

Resume lines:
<resume_lines>
{lines}
</resume_lines>

Return exactly one review for every line_id, in the supplied order, with no extra IDs. The contact header is intentionally excluded. Company, historical title, and date are locked context and must not be changed. Recommend keep, rewrite, remove, or ask, but do not make any decision on the user's behalf. Preserve every verified work position with at least one substantive achievement bullet. Suggested_text must be a complete LaTeX-ready bullet body without a leading \\item. A remove action is only a recommendation. If an improvement needs a fact absent from root _resume.tex, use ask, supply a precise question, and do not put that fact in suggested_text. Score relevance to this specific job from 1 to 10. Suggest a lowercase hyphenated company-role folder slug.
"""


def _single_line_review_prompt(
    record: dict[str, Any],
    current_text: str,
    job_description: str,
    instruction: str,
    confirmed_facts: list[str],
) -> str:
    confirmations = "\n".join(f"- {fact}" for fact in confirmed_facts) or "- None"
    return f"""Reconsider exactly one resume line using the user's instruction.

Line ID: {record['id']}
Section: {record['section']}
Entry: {record['entry_title']}
Locked historical title/category: {record['entry_subtitle']}
Locked date: {record['date']}
Current LaTeX bullet body: {current_text}

Job description:
{job_description}

User instruction:
{instruction}

Explicitly confirmed facts:
{confirmations}

Return the same line_id. Suggested_text must be a complete LaTeX-ready bullet body without a leading \\item. Preserve verified facts. If the instruction needs an unverified fact, use action ask and ask one precise question instead of inventing it.
"""


def _normalize_batch_reviews(
    proposal: dict[str, Any], records: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    expected = [record["id"] for record in records]
    returned = [review.get("line_id") for review in proposal.get("reviews", [])]
    if returned != expected:
        missing = [line_id for line_id in expected if line_id not in returned]
        extra = [line_id for line_id in returned if line_id not in expected]
        details: list[str] = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unexpected " + ", ".join(str(item) for item in extra))
        if not details:
            details.append("reviews were not returned in source order")
        raise CodexBackendError("Incomplete line review: " + "; ".join(details))
    return {review["line_id"]: review for review in proposal["reviews"]}


def _current_line_text(session: Session, line_id: str) -> str:
    decision = session.payload.get("decisions", {}).get(line_id, {})
    if decision.get("action") == "rewrite":
        return decision.get("text", "")
    return session.payload["line_records"][line_id]["text"]


def _show_interactive_line(
    session: Session,
    record: dict[str, Any],
    recommendation: dict[str, Any],
    position: int,
    total: int,
) -> None:
    current_decision = session.payload.get("decisions", {}).get(record["id"])
    parts = [
        f"[bold]Locked context[/bold]\n{record['entry_title']} · {record['entry_subtitle']} · {record['date']}",
        f"[bold]Current[/bold]\n{tex_to_text(_current_line_text(session, record['id']))}",
        f"[bold]Codex recommendation[/bold]\n{recommendation['action']} · relevance {recommendation['relevance_score']}/10\n{recommendation['reason']}",
    ]
    if recommendation.get("suggested_text"):
        parts.append(f"[bold]Suggested[/bold]\n{tex_to_text(recommendation['suggested_text'])}")
    if recommendation.get("question"):
        parts.append(f"[yellow]Question[/yellow]\n{recommendation['question']}")
    if current_decision:
        parts.append(f"[dim]Saved decision: {current_decision['action']}[/dim]")
    console.print(
        Panel(
            "\n\n".join(parts),
            title=f"{record['section']} · line {position}/{total}",
        )
    )


def _interactive_snapshot(session: Session) -> None:
    session.history.append(
        json.dumps(
            {
                "kind": "interactive-tailor",
                "decisions": session.payload.get("decisions", {}),
                "cursor": session.cursor,
                "fit_skipped": session.payload.get("fit_skipped", []),
            },
            ensure_ascii=False,
        )
    )


def _interactive_undo(session: Session) -> bool:
    while session.history:
        value = json.loads(session.history.pop())
        if value.get("kind") != "interactive-tailor":
            continue
        session.payload["decisions"] = value["decisions"]
        session.payload["fit_skipped"] = value.get("fit_skipped", [])
        session.cursor = value["cursor"]
        session.working_tex = apply_line_decisions(
            session.payload["base_tex"], session.payload["decisions"]
        )
        return True
    return False


def _apply_interactive_decision(
    session: Session,
    root_source: str,
    line_id: str,
    action: str,
    text: str = "",
) -> list[str]:
    _interactive_snapshot(session)
    decision = {"action": action}
    if action == "rewrite":
        replacement = text.strip()
        if not replacement:
            session.history.pop()
            return ["A rewritten line cannot be empty"]
        decision["text"] = replacement
    session.payload.setdefault("decisions", {})[line_id] = decision
    candidate = apply_line_decisions(session.payload["base_tex"], session.payload["decisions"])
    errors = [
        *validate_tailored_tex(root_source, candidate, _confirmed_facts(session)),
        *validate_tailored_completeness(root_source, candidate),
    ]
    if errors:
        _interactive_undo(session)
        return errors
    session.working_tex = candidate
    return []


def _request_single_line_review(
    chat: CodexConversation,
    session: Session,
    record: dict[str, Any],
    instruction: str,
) -> dict[str, Any]:
    with console.status("Codex is reconsidering this line..."):
        proposal = chat.run_json(
            _single_line_review_prompt(
                record,
                _current_line_text(session, record["id"]),
                session.job_description,
                instruction,
                _confirmed_facts(session),
            ),
            LINE_REVIEW_SCHEMA,
        )
    if proposal.get("line_id") != record["id"]:
        raise CodexBackendError(
            f"Codex reviewed {proposal.get('line_id')!r} instead of {record['id']!r}"
        )
    return proposal


def _initialize_interactive_tailor(
    session: Session, root_source: str, requested_slug: str | None
) -> None:
    previous_target = session.target
    base_tex = prepare_interactive_tailored_source(root_source)
    records = _line_records(base_tex)
    session.target = ""
    session.cursor = 0
    session.working_tex = base_tex
    session.history = []
    session.payload = {
        "workflow_version": 2,
        "phase": "recommendations",
        "requested_slug": requested_slug or previous_target or "",
        "base_tex": base_tex,
        "line_ids": [record["id"] for record in records],
        "line_records": {record["id"]: record for record in records},
        "decisions": {},
        "recommendations": {},
        "confirmed_facts": [],
        "fit_skipped": [],
    }


def _review_tailored_lines(
    chat: CodexConversation, session: Session, root_source: str
) -> bool:
    store = SessionStore(REPO_ROOT)
    line_ids: list[str] = session.payload["line_ids"]
    records: dict[str, dict[str, Any]] = session.payload["line_records"]
    recommendations: dict[str, dict[str, Any]] = session.payload["recommendations"]
    while session.cursor < len(line_ids):
        line_id = line_ids[session.cursor]
        record = records[line_id]
        proposal = recommendations[line_id]
        _show_interactive_line(session, record, proposal, session.cursor + 1, len(line_ids))
        answer = console.input(
            "[bold]You[/bold] ([cyan]/accept /keep /remove /regenerate /back /undo /quit[/cyan], or instruction): "
        ).strip()
        command = answer.casefold()
        if command in {"/quit", "quit", "q"}:
            store.save(session)
            console.print(f"Session saved as [bold]{session.id}[/bold].")
            return False
        if command in {"/undo", "undo"}:
            console.print("Undid the latest decision." if _interactive_undo(session) else "[dim]Nothing to undo.[/dim]")
            store.save(session)
            continue
        if command in {"/back", "back"}:
            session.cursor = max(0, session.cursor - 1)
            store.save(session)
            continue
        if command in {"/regenerate", "regenerate"}:
            proposal = _request_single_line_review(
                chat,
                session,
                record,
                "Give a materially different recommendation while preserving verified facts.",
            )
            recommendations[line_id] = proposal
            store.save(session)
            continue
        if command in {"/keep", "keep"}:
            errors = _apply_interactive_decision(session, root_source, line_id, "keep")
        elif command in {"/remove", "remove"}:
            errors = _apply_interactive_decision(session, root_source, line_id, "remove")
        elif command in {"/accept", "accept"}:
            if proposal["action"] == "ask" or proposal["uses_unverified_fact"]:
                question = proposal.get("question") or "What verified fact supports this change?"
                fact = console.input(f"[yellow]{question}[/yellow]\nYou: ").strip()
                if not fact:
                    console.print("[yellow]No decision was saved without factual confirmation.[/yellow]")
                    continue
                _record_confirmed_fact(session, fact)
                recommendations[line_id] = _request_single_line_review(
                    chat,
                    session,
                    record,
                    f"The user explicitly confirmed this fact: {fact}",
                )
                store.save(session)
                continue
            action = proposal["action"]
            if action == "rewrite":
                errors = _apply_interactive_decision(
                    session, root_source, line_id, "rewrite", proposal["suggested_text"]
                )
            elif action == "remove":
                errors = _apply_interactive_decision(session, root_source, line_id, "remove")
            else:
                errors = _apply_interactive_decision(session, root_source, line_id, "keep")
        elif answer:
            recommendations[line_id] = _request_single_line_review(
                chat, session, record, answer
            )
            store.save(session)
            continue
        else:
            console.print("[dim]Choose a command so this line receives an explicit decision.[/dim]")
            continue

        if errors:
            console.print("[red]That decision would violate the resume rules:[/red]")
            for error in errors:
                console.print(f"  • {error}")
            continue
        session.cursor += 1
        store.save(session)
    session.payload["phase"] = "page_fit"
    store.save(session)
    return True


def _preview_tailored_build(session: Session) -> BuildResult:
    preview_parent = REPO_ROOT / "tmp"
    preview_parent.mkdir(parents=True, exist_ok=True)
    preview = Path(tempfile.mkdtemp(prefix=f"resume-preview-{session.id}-", dir=preview_parent))
    try:
        (preview / "_resume.tex").write_text(session.working_tex, encoding="utf-8")
        return build_resume(REPO_ROOT, str(preview.relative_to(REPO_ROOT)))
    finally:
        shutil.rmtree(preview, ignore_errors=True)
        try:
            preview_parent.rmdir()
        except OSError:
            pass


def _fit_candidate_ids(session: Session) -> list[str]:
    skipped = set(session.payload.get("fit_skipped", []))
    decisions = session.payload.get("decisions", {})
    recommendations = session.payload["recommendations"]
    records = session.payload["line_records"]
    order = {line_id: index for index, line_id in enumerate(session.payload["line_ids"])}
    candidates = [
        line_id
        for line_id in session.payload["line_ids"]
        if decisions.get(line_id, {}).get("action") != "remove" and line_id not in skipped
    ]
    return sorted(
        candidates,
        key=lambda line_id: (
            0 if records[line_id]["is_metadata"] else 1,
            recommendations[line_id]["relevance_score"],
            order[line_id],
        ),
    )


def _fit_tailored_interactively(
    chat: CodexConversation, session: Session, root_source: str
) -> bool:
    store = SessionStore(REPO_ROOT)
    while True:
        with console.status("Building a temporary page-count preview..."):
            preview = _preview_tailored_build(session)
        pages = preview.report.pages
        if pages == 1:
            session.payload["phase"] = "ready_to_save"
            store.save(session)
            return True
        console.print(
            Panel(
                f"The reviewed draft is [bold]{pages} pages[/bold]. Nothing will be removed automatically. "
                "Choose how to tighten one line at a time.",
                title="Interactive one-page fit",
                style="yellow",
            )
        )
        candidates = _fit_candidate_ids(session)
        if not candidates:
            session.payload["fit_skipped"] = []
            store.save(session)
            raise BuildError(
                "The draft is still longer than one page after every remaining line was kept. "
                "Resume the session to reconsider those choices."
            )
        line_id = candidates[0]
        record = session.payload["line_records"][line_id]
        recommendation = session.payload["recommendations"][line_id]
        _show_interactive_line(session, record, recommendation, 1, len(candidates))
        answer = console.input(
            "Fit ([cyan]/shorten /remove /keep /undo /quit[/cyan], or a shortening instruction): "
        ).strip()
        command = answer.casefold()
        if command in {"/quit", "quit", "q"}:
            store.save(session)
            console.print(f"Session saved as [bold]{session.id}[/bold].")
            return False
        if command in {"/undo", "undo"}:
            console.print("Undid the latest decision." if _interactive_undo(session) else "[dim]Nothing to undo.[/dim]")
            store.save(session)
            continue
        if command in {"/keep", "keep", ""}:
            session.payload.setdefault("fit_skipped", []).append(line_id)
            store.save(session)
            continue
        if command in {"/remove", "remove"}:
            errors = _apply_interactive_decision(session, root_source, line_id, "remove")
            if errors:
                console.print("[red]That line cannot be removed:[/red] " + "; ".join(errors))
            store.save(session)
            continue
        instruction = (
            f"Shorten this line materially to help a {pages}-page resume fit one page. Preserve its strongest job-relevant evidence."
            if command in {"/shorten", "shorten"}
            else answer
        )
        proposal = _request_single_line_review(chat, session, record, instruction)
        _show_interactive_line(session, record, proposal, 1, len(candidates))
        if proposal["action"] == "ask" or proposal["uses_unverified_fact"]:
            fact = console.input(f"[yellow]{proposal['question']}[/yellow]\nYou: ").strip()
            if fact:
                _record_confirmed_fact(session, fact)
            store.save(session)
            continue
        suggested = proposal.get("suggested_text", "").strip()
        if proposal["action"] != "rewrite" or not suggested:
            console.print("[yellow]Codex did not produce a shorter rewrite; the line remains unchanged.[/yellow]")
            session.payload.setdefault("fit_skipped", []).append(line_id)
            store.save(session)
            continue
        if not typer.confirm("Use this shorter line?", default=True):
            session.payload.setdefault("fit_skipped", []).append(line_id)
            store.save(session)
            continue
        errors = _apply_interactive_decision(
            session, root_source, line_id, "rewrite", suggested
        )
        if errors:
            console.print("[red]That rewrite failed validation:[/red] " + "; ".join(errors))
        else:
            session.payload.setdefault("fit_skipped", []).append(line_id)
        store.save(session)


def _finalize_interactive_tailor(
    chat: CodexConversation, session: Session, root_source: str
) -> None:
    store = SessionStore(REPO_ROOT)
    errors = [
        *validate_tailored_tex(root_source, session.working_tex, _confirmed_facts(session)),
        *validate_tailored_completeness(root_source, session.working_tex),
    ]
    if errors:
        raise ValueError("Final resume validation failed: " + "; ".join(errors))
    audit_errors = _factual_audit(chat, session.working_tex, _confirmed_facts(session))
    if audit_errors:
        raise ValueError("Final factual audit failed: " + "; ".join(audit_errors))

    target = session.target
    source_path = REPO_ROOT / target / "_resume.tex"
    current_source = source_path.read_text(encoding="utf-8") if source_path.exists() else ""
    if source_hash(current_source) != session.original_hash:
        raise RuntimeError(f"{target}/_resume.tex changed during this session; refusing to overwrite it")
    _show_diff(current_source or root_source, session.working_tex)
    if not typer.confirm(f"Save and build {target}/Morgan_Le_Resume.pdf?", default=True):
        store.save(session)
        console.print(f"Session saved as [bold]{session.id}[/bold].")
        return

    folder = source_path.parent
    pdf_path = folder / "Morgan_Le_Resume.pdf"
    previous_pdf = pdf_path.read_bytes() if pdf_path.exists() else None
    folder.mkdir(parents=True, exist_ok=True)
    source_path.write_text(session.working_tex, encoding="utf-8")
    try:
        result = build_resume(REPO_ROOT, target)
        if result.report.pages != 1:
            raise BuildError(
                f"Final build has {result.report.pages} pages; expected exactly one"
            )
        _visual_pdf_qa(chat, result.report)
    except Exception:
        if current_source:
            source_path.write_text(current_source, encoding="utf-8")
        else:
            source_path.unlink(missing_ok=True)
        if previous_pdf is not None:
            pdf_path.write_bytes(previous_pdf)
        else:
            pdf_path.unlink(missing_ok=True)
        try:
            folder.rmdir()
        except OSError:
            pass
        raise

    session.complete = True
    session.payload["phase"] = "complete"
    store.save(session)
    console.print(
        Panel(
            f"Created [bold]{target}/Morgan_Le_Resume.pdf[/bold]\n"
            f"Pages: 1 | A4: yes | Links: {result.report.links} | "
            f"Text characters: {sum(result.report.extracted_characters)}",
            title="Tailored resume ready",
            style="green",
        )
    )


def _run_tailor_session(session: Session, *, requested_slug: str | None = None, assume_yes: bool = False) -> None:
    if assume_yes:
        raise typer.BadParameter(
            "--yes is unavailable in interactive tailoring because every line requires a user decision"
        )
    store = SessionStore(REPO_ROOT)
    root_source = (REPO_ROOT / "_resume.tex").read_text(encoding="utf-8")
    if session.payload.get("workflow_version") != 2:
        _initialize_interactive_tailor(session, root_source, requested_slug)
        store.save(session)
    elif requested_slug and not session.payload.get("requested_slug"):
        session.payload["requested_slug"] = requested_slug
        store.save(session)

    with CodexConversation(REPO_ROOT, session.thread_id) as chat:
        session.thread_id = chat.thread_id
        store.save(session)
        if session.payload["phase"] == "recommendations":
            records = [
                session.payload["line_records"][line_id]
                for line_id in session.payload["line_ids"]
            ]
            with console.status("Codex is reviewing every resume line in one batch..."):
                batch = chat.run_json(
                    _batch_line_review_prompt(records, session.job_description),
                    LINE_REVIEW_BATCH_SCHEMA,
                )
            session.payload["recommendations"] = _normalize_batch_reviews(batch, records)
            session.payload["suggested_slug"] = batch["suggested_slug"]
            session.payload["summary"] = batch["summary"]
            session.payload["phase"] = "line_review"
            store.save(session)
            _show_tailor_proposal(
                {
                    "summary": batch["summary"],
                    "suggested_slug": batch["suggested_slug"],
                    "questions": [],
                }
            )

        if session.payload["phase"] == "line_review":
            if not _review_tailored_lines(chat, session, root_source):
                return

        if not session.target:
            target, _ = _choose_slug(
                {"suggested_slug": session.payload["suggested_slug"]},
                session.payload.get("requested_slug") or None,
                False,
            )
            existing_source = REPO_ROOT / target / "_resume.tex"
            previous = existing_source.read_text(encoding="utf-8") if existing_source.exists() else ""
            session.target = target
            session.original_hash = source_hash(previous)
            store.save(session)

        if session.payload["phase"] == "page_fit":
            if not _fit_tailored_interactively(chat, session, root_source):
                return

        if session.payload["phase"] == "ready_to_save":
            _finalize_interactive_tailor(chat, session, root_source)


@app.command()
def tailor(
    job_text: str | None = typer.Option(None, "--job-text", help="Job description text; otherwise paste interactively."),
    slug: str | None = typer.Option(None, help="Preferred output folder slug."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Unsupported: tailoring requires a decision for every line."),
) -> None:
    """Build a one-page tailored resume through a line-by-line session."""
    if yes:
        raise typer.BadParameter("--yes cannot skip the required line-by-line review")
    _require_authentication()
    description = job_text.strip() if job_text else _read_multiline("Paste the job description:")
    session = Session.create(mode="tailor", target="", job_description=description)
    SessionStore(REPO_ROOT).save(session)
    try:
        _run_tailor_session(session, requested_slug=slug, assume_yes=yes)
    except (CodexBackendError, BuildError, OSError, ValueError, KeyError) as exc:
        console.print(Panel(str(exc), title="Tailoring failed", style="red"))
        raise typer.Exit(1) from exc


def _review_prompt(bullet: Any, job_description: str, instruction: str = "") -> str:
    job_context = job_description or "No job description was supplied. Evaluate this as a strong general resume bullet."
    instruction_block = f"\nUser instruction: {instruction}\n" if instruction else ""
    return f"""Review this resume bullet.

Section: {bullet.section}
Entry: {bullet.entry_title}
Historical title/category: {bullet.entry_subtitle}
Bullet ID: {bullet.id}
Current LaTeX bullet body: {bullet.text}

Job context:
{job_context}
{instruction_block}
Assess relevance, clarity, specificity, impact, and factual grounding. Suggested_text must be a LaTeX-ready bullet body without a leading \\item. Use only verified facts. If an additional fact would materially improve it, set recommendation to ask, put the question in question, and do not include that unverified fact in suggested_text.
"""


def _show_bullet_review(bullet: Any, proposal: dict[str, Any], position: int, total: int) -> None:
    scores = (
        f"Relevance {proposal['relevance_score']}/10 · "
        f"Clarity {proposal['clarity_score']}/10 · Impact {proposal['impact_score']}/10"
    )
    body = [f"[bold]Current[/bold]\n{tex_to_text(bullet.text)}", f"[bold]Scores[/bold]\n{scores}"]
    if proposal["strengths"]:
        body.append("[bold]Strengths[/bold]\n" + "\n".join(f"• {item}" for item in proposal["strengths"]))
    if proposal["concerns"]:
        body.append("[bold]Concerns[/bold]\n" + "\n".join(f"• {item}" for item in proposal["concerns"]))
    if proposal["suggested_text"]:
        body.append(f"[bold]Suggested[/bold]\n{tex_to_text(proposal['suggested_text'])}")
    if proposal["question"]:
        body.append(f"[yellow]Question[/yellow]\n{proposal['question']}")
    console.print(
        Panel(
            "\n\n".join(body),
            title=f"{bullet.section} · {bullet.entry_title} · bullet {position}/{total}",
        )
    )


def _snapshot(session: Session) -> None:
    session.history.append(
        json.dumps(
            {
                "working_tex": session.working_tex,
                "source_appends": session.source_appends,
                "bullet_records": session.payload.get("bullet_records", {}),
            },
            ensure_ascii=False,
        )
    )


def _undo(session: Session) -> bool:
    if not session.history:
        return False
    value = json.loads(session.history.pop())
    session.working_tex = value["working_tex"]
    session.source_appends = value["source_appends"]
    if "bullet_records" in value:
        session.payload["bullet_records"] = value["bullet_records"]
    return True


def _record_confirmed_fact(session: Session, value: str) -> None:
    value = value.strip()
    if value and value not in session.payload.setdefault("confirmed_facts", []):
        session.payload["confirmed_facts"].append(value)


def _section_prompt(document: ResumeDocument, section: str, job_description: str, target_is_root: bool, instruction: str = "") -> str:
    lines: list[str] = []
    for entry in document.entries:
        if entry.section != section:
            continue
        lines.append(f"Entry: {entry.title} — {entry.subtitle}")
        for bullet in entry.bullets:
            lines.append(f"  {bullet.id}: {tex_to_text(bullet.text)}")
    allowed = (
        "Because this is the root source, propose only keep or add actions; never replace or remove."
        if target_is_root
        else "For this tailored version, you may propose keep, replace, remove, or add actions."
    )
    instruction_block = f"\nUser instruction: {instruction}\n" if instruction else ""
    return f"""Review this complete resume section after its bullets have been reviewed.

Section: {section}
Job context: {job_description or 'General resume review; no job description supplied.'}
{allowed}

Current entries and bullet IDs:
{chr(10).join(lines)}
{instruction_block}
Check repetition, ordering, allocation of space, relevance, and whether the section works as a whole. Each action must refer to an exact bullet_id for replace/remove, or an exact entry_title for add. Text must be a LaTeX-ready bullet body without \\item. Use only verified facts.
"""


def _show_section_review(section: str, proposal: dict[str, Any]) -> None:
    lines = [proposal["summary"]]
    if proposal["strengths"]:
        lines.append("Strengths:\n" + "\n".join(f"• {item}" for item in proposal["strengths"]))
    if proposal["concerns"]:
        lines.append("Concerns:\n" + "\n".join(f"• {item}" for item in proposal["concerns"]))
    if proposal["actions"]:
        lines.append(
            "Actions:\n"
            + "\n".join(
                f"• {item['action']} {item['bullet_id'] or item['entry_title']}: {item['reason']}"
                for item in proposal["actions"]
                if item["action"] != "keep"
            )
        )
    console.print(Panel("\n\n".join(lines), title=f"Section review · {section}"))


def _resolve_bullet_id(source: str, original_id: str, entry_title: str) -> str | None:
    document = parse_resume(source)
    try:
        return document.bullet(original_id).id
    except KeyError:
        return None


def _review_bullet_from_session(session: Session, bullet_id: str) -> Any:
    document = parse_resume(session.working_tex)
    record = session.payload.get("bullet_records", {}).get(bullet_id, {})
    expected_title = record.get("entry_title", "")
    expected_text = record.get("text", "")
    try:
        candidate = document.bullet(bullet_id)
        if (
            (not expected_title or candidate.entry_title == expected_title)
            and (not expected_text or candidate.text == expected_text)
        ):
            return candidate
    except KeyError:
        pass
    for entry in document.entries:
        if expected_title and entry.title != expected_title:
            continue
        for bullet in entry.bullets:
            if bullet.text == expected_text:
                return bullet
    raise KeyError(f"Review bullet no longer exists: {bullet_id}")


def _apply_section_actions(session: Session, actions: list[dict[str, Any]], *, add_to_source: bool) -> None:
    target_is_root = session.target in {"", ".", "root"}
    _snapshot(session)
    removals: list[dict[str, Any]] = []
    for action in actions:
        kind = action["action"]
        text = action["text"].strip()
        if kind == "keep":
            continue
        if kind == "remove":
            if not target_is_root:
                removals.append(action)
            continue
        if kind == "replace":
            bullet_id = _resolve_bullet_id(session.working_tex, action["bullet_id"], action["entry_title"])
            if not bullet_id or not text:
                continue
            if target_is_root:
                entry_id = parse_resume(session.working_tex).bullet(bullet_id).entry_id
                session.working_tex = append_bullet(session.working_tex, entry_id, text)
            else:
                session.working_tex = replace_bullet(session.working_tex, bullet_id, text)
                if action["bullet_id"] in session.payload.get("bullet_records", {}):
                    session.payload["bullet_records"][action["bullet_id"]]["text"] = text
                if add_to_source:
                    session.source_appends.append({"entry_title": action["entry_title"], "text": text})
        elif kind == "add" and text:
            current = parse_resume(session.working_tex)
            entries = [entry for entry in current.entries if entry.title.casefold() == action["entry_title"].casefold()]
            if len(entries) == 1:
                session.working_tex = append_bullet(session.working_tex, entries[0].id, text)
                if add_to_source and not target_is_root:
                    session.source_appends.append({"entry_title": action["entry_title"], "text": text})
    for action in reversed(removals):
        bullet_id = _resolve_bullet_id(session.working_tex, action["bullet_id"], action["entry_title"])
        if bullet_id:
            session.working_tex = remove_bullet(session.working_tex, bullet_id)


def _review_section(chat: CodexConversation, session: Session, section: str) -> None:
    store = SessionStore(REPO_ROOT)
    instruction = ""
    while True:
        document = parse_resume(session.working_tex)
        with console.status(f"Codex is reviewing the {section} section..."):
            proposal = chat.run_json(
                _section_prompt(
                    document,
                    section,
                    session.job_description,
                    session.target in {"", ".", "root"},
                    instruction,
                ),
                SECTION_REVIEW_SCHEMA,
            )
        _show_section_review(section, proposal)
        answer = console.input(
            "Section ([cyan]/accept[/cyan], [cyan]/source[/cyan], [cyan]/continue[/cyan], or instruction): "
        ).strip()
        command = answer.casefold()
        if command in {"", "/continue", "continue", "/skip"}:
            return
        if command in {"/accept", "accept"}:
            _apply_section_actions(session, proposal["actions"], add_to_source=False)
            store.save(session)
            return
        if command in {"/source", "source"}:
            _apply_section_actions(session, proposal["actions"], add_to_source=True)
            store.save(session)
            return
        instruction = answer
        _record_confirmed_fact(session, instruction)


def _finish_review(session: Session, chat: CodexConversation) -> None:
    store = SessionStore(REPO_ROOT)
    target_path = resume_path(REPO_ROOT, session.target)
    original_tex = session.payload.get("original_tex", "")
    _show_diff(original_tex, session.working_tex)
    if session.source_appends:
        console.print(f"[yellow]{len(session.source_appends)} accepted bullet(s) will be appended to the root source.[/yellow]")
    if not typer.confirm("Save these changes and build the PDF?", default=True):
        console.print(f"Session saved as [bold]{session.id}[/bold].")
        return

    current_target = target_path.read_text(encoding="utf-8")
    if source_hash(current_target) != session.original_hash:
        raise RuntimeError("The target _resume.tex changed during this session; refusing to overwrite it")

    root_path = REPO_ROOT / "_resume.tex"
    root_before = root_path.read_text(encoding="utf-8")
    root_candidate = session.working_tex if session.target in {"", ".", "root"} else root_before
    if session.target not in {"", ".", "root"}:
        for addition in session.source_appends:
            root_candidate = append_bullet_by_title(root_candidate, addition["entry_title"], addition["text"])
        errors = validate_tailored_tex(root_candidate, session.working_tex, _confirmed_facts(session))
        if errors:
            raise ValueError("Tailored resume failed final validation: " + "; ".join(errors))
        audit_errors = _factual_audit(chat, session.working_tex, _confirmed_facts(session))
        if audit_errors:
            raise ValueError("Tailored resume failed factual audit: " + "; ".join(audit_errors))
    elif root_candidate != root_before:
        audit_errors = _factual_audit(chat, root_candidate, _confirmed_facts(session))
        if audit_errors:
            raise ValueError("Root additions failed factual audit: " + "; ".join(audit_errors))
    append_errors = validate_root_append_only(root_before, root_candidate)
    if append_errors:
        raise ValueError("Root append-only validation failed: " + "; ".join(append_errors))

    target_path.write_text(session.working_tex, encoding="utf-8")
    try:
        if session.target in {"", ".", "root"}:
            result = build_resume(REPO_ROOT, ".")
            _visual_pdf_qa(chat, result.report)
        else:
            result = _build_tailored_until_one_page(
                chat=chat,
                session=session,
                root_source=root_candidate,
                target=session.target,
                confirm_revisions=True,
            )
    except Exception:
        target_path.write_text(current_target, encoding="utf-8")
        try:
            build_resume(REPO_ROOT, session.target)
        except BuildError:
            pass
        raise

    if session.target not in {"", ".", "root"} and root_candidate != root_before:
        root_path.write_text(root_candidate, encoding="utf-8")
        try:
            root_result = build_resume(REPO_ROOT, ".")
            _visual_pdf_qa(chat, root_result.report)
        except Exception:
            root_path.write_text(root_before, encoding="utf-8")
            target_path.write_text(current_target, encoding="utf-8")
            try:
                build_resume(REPO_ROOT, session.target)
                build_resume(REPO_ROOT, ".")
            except BuildError:
                pass
            raise
        console.print(
            f"Root source updated append-only and rebuilt ({root_result.report.pages} pages, {root_result.report.links} links)."
        )

    session.complete = True
    session.working_tex = target_path.read_text(encoding="utf-8")
    store.save(session)
    console.print(
        Panel(
            f"Built [bold]{result.report.path.relative_to(REPO_ROOT)}[/bold]\n"
            f"Pages: {result.report.pages} | A4: yes | Links: {result.report.links} | "
            f"Text characters: {sum(result.report.extracted_characters)}",
            title="Review complete",
            style="green",
        )
    )


def _run_review_session(session: Session) -> None:
    store = SessionStore(REPO_ROOT)
    original_ids: list[str] = session.payload["bullet_ids"]
    original_sections: dict[str, str] = session.payload["bullet_sections"]
    reviewed_sections: list[str] = session.payload.setdefault("reviewed_sections", [])
    with CodexConversation(REPO_ROOT, session.thread_id) as chat:
        session.thread_id = chat.thread_id
        store.save(session)
        while session.cursor < len(original_ids):
            bullet_id = original_ids[session.cursor]
            try:
                bullet = _review_bullet_from_session(session, bullet_id)
            except KeyError:
                session.cursor += 1
                store.save(session)
                continue
            instruction = ""
            moved_back = False
            while True:
                with console.status("Codex is reviewing this bullet..."):
                    proposal = chat.run_json(
                        _review_prompt(bullet, session.job_description, instruction),
                        BULLET_REVIEW_SCHEMA,
                    )
                _show_bullet_review(bullet, proposal, session.cursor + 1, len(original_ids))
                answer = console.input(
                    "[bold]You[/bold] ([cyan]/accept /keep /source /regenerate /back /undo /done[/cyan], or instruction): "
                ).strip()
                command = answer.casefold()
                if command in {"/done", "done"}:
                    _finish_review(session, chat)
                    return
                if command in {"/undo", "undo"}:
                    console.print("Undid the latest edit." if _undo(session) else "[dim]Nothing to undo.[/dim]")
                    store.save(session)
                    bullet = _review_bullet_from_session(session, bullet_id)
                    continue
                if command in {"/back", "back"}:
                    session.cursor = max(0, session.cursor - 1)
                    moved_back = True
                    store.save(session)
                    break
                if command in {"/keep", "keep", "/skip", "skip", ""}:
                    session.cursor += 1
                    store.save(session)
                    break
                if command in {"/regenerate", "regenerate"}:
                    instruction = "Provide a materially different rewrite while preserving verified facts."
                    continue
                if command in {"/accept", "accept", "/source", "source"}:
                    suggested = proposal["suggested_text"].strip()
                    if not suggested or proposal["recommendation"] == "keep":
                        session.cursor += 1
                        store.save(session)
                        break
                    if proposal["uses_unverified_fact"] or proposal["recommendation"] == "ask":
                        question = proposal["question"] or "What factual information supports this proposed change?"
                        fact = console.input(f"[yellow]{question}[/yellow]\nYou: ").strip()
                        if not fact:
                            console.print("[yellow]Proposal not accepted without factual confirmation.[/yellow]")
                            continue
                        _record_confirmed_fact(session, fact)
                        instruction = f"The user explicitly confirmed this fact: {fact}. Revise the bullet using only that confirmation."
                        continue
                    _snapshot(session)
                    if session.target in {"", ".", "root"}:
                        session.working_tex = append_bullet(session.working_tex, bullet.entry_id, suggested)
                    else:
                        session.working_tex = replace_bullet(session.working_tex, bullet.id, suggested)
                        session.payload["bullet_records"][bullet_id]["text"] = suggested
                        if command in {"/source", "source"}:
                            session.source_appends.append({"entry_title": bullet.entry_title, "text": suggested})
                    session.cursor += 1
                    store.save(session)
                    break
                instruction = answer
                _record_confirmed_fact(session, answer)

            if moved_back:
                continue
            if session.cursor == 0:
                continue
            completed_id = original_ids[session.cursor - 1]
            section = original_sections[completed_id]
            next_section = original_sections.get(original_ids[session.cursor]) if session.cursor < len(original_ids) else None
            if section != next_section and section not in reviewed_sections:
                _review_section(chat, session, section)
                reviewed_sections.append(section)
                store.save(session)

        _finish_review(session, chat)


@app.command()
def review(
    target: str = typer.Argument(".", help="Root (.) or an existing tailored folder."),
    job_text: str | None = typer.Option(None, "--job-text", help="Optional job description text."),
    no_job: bool = typer.Option(False, "--no-job", help="Skip the optional job-description prompt."),
    include_metadata: bool = typer.Option(False, "--include-metadata", help="Also review Technologies/Tools bullets."),
) -> None:
    """Review a resume bullet by bullet and section by section."""
    _require_authentication()
    path = resume_path(REPO_ROOT, target)
    if not path.is_file():
        raise typer.BadParameter(f"Resume source not found: {path}")
    if job_text is not None:
        description = job_text.strip()
    elif no_job:
        description = ""
    elif typer.confirm("Use a job description for this review?", default=False):
        description = _read_multiline("Paste the optional job description:", optional=True)
    else:
        description = ""
    source = path.read_text(encoding="utf-8")
    document = parse_resume(source)
    bullets = [bullet for entry in document.entries for bullet in entry.bullets if include_metadata or not bullet.is_metadata]
    if not bullets:
        console.print("No reviewable bullets found.")
        raise typer.Exit(0)
    session = Session.create(mode="review", target=target, job_description=description)
    session.working_tex = source
    session.original_hash = source_hash(source)
    session.payload = {
        "original_tex": source,
        "bullet_ids": [bullet.id for bullet in bullets],
        "bullet_sections": {bullet.id: bullet.section for bullet in bullets},
        "bullet_records": {
            bullet.id: {"entry_title": bullet.entry_title, "text": bullet.text}
            for bullet in bullets
        },
        "reviewed_sections": [],
        "confirmed_facts": [],
    }
    SessionStore(REPO_ROOT).save(session)
    try:
        _run_review_session(session)
    except (CodexBackendError, BuildError, OSError, RuntimeError, ValueError, KeyError) as exc:
        console.print(Panel(str(exc), title="Review stopped", style="red"))
        console.print(f"Session remains resumable as [bold]{session.id}[/bold].")
        raise typer.Exit(1) from exc


@app.command("resume")
def resume_command(session_id: str | None = typer.Argument(None, help="Session ID; defaults to the latest unfinished session.")) -> None:
    """Continue an unfinished tailoring or review conversation."""
    _require_authentication()
    store = SessionStore(REPO_ROOT)
    try:
        session = store.load(session_id) if session_id else store.latest()
    except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
        console.print(Panel(str(exc), title="Cannot resume", style="red"))
        raise typer.Exit(1) from exc
    console.print(f"Resuming [bold]{session.mode}[/bold] session [bold]{session.id}[/bold].")
    try:
        if session.mode == "tailor":
            _run_tailor_session(session)
        elif session.mode == "review":
            _run_review_session(session)
        else:
            raise ValueError(f"Unknown session mode: {session.mode}")
    except (CodexBackendError, BuildError, OSError, RuntimeError, ValueError, KeyError) as exc:
        console.print(Panel(str(exc), title="Session stopped", style="red"))
        raise typer.Exit(1) from exc


@app.command()
def status() -> None:
    """Check Codex authentication, resume parsing, variants, and sessions."""
    authenticated, auth_output = authentication_status()
    root = parse_resume((REPO_ROOT / "_resume.tex").read_text(encoding="utf-8"))
    variants = sorted(
        path.name
        for path in REPO_ROOT.iterdir()
        if path.is_dir() and (path / "_resume.tex").is_file() and not path.name.startswith(".")
    )
    unfinished = SessionStore(REPO_ROOT).unfinished()
    table = Table(title="Resume CLI status")
    table.add_column("Check")
    table.add_column("Result")
    table.add_row("Codex authentication", "Ready" if authenticated else auth_output or "Not authenticated")
    table.add_row("Root entries", str(len(root.entries)))
    table.add_row("Root bullets", str(sum(len(entry.bullets) for entry in root.entries)))
    table.add_row("Tailored versions", ", ".join(variants) or "None")
    table.add_row("Unfinished sessions", str(len(unfinished)))
    table.add_row("Tectonic", shutil.which("tectonic") or "Not found")
    console.print(table)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Open the interactive menu when no subcommand is supplied."""
    if ctx.invoked_subcommand is not None:
        return
    console.print(Panel("Create or review a resume through a focused Codex conversation.", title="Resume CLI"))
    console.print("1. Create a tailored resume")
    console.print("2. Review a resume interactively")
    console.print("3. Resume the latest session")
    console.print("4. Show status")
    choice = console.input("Choose a mode [1]: ").strip() or "1"
    if choice == "1":
        tailor(job_text=None, slug=None, yes=False)
    elif choice == "2":
        target = console.input("Resume folder [.]: ").strip() or "."
        review(target=target, job_text=None, no_job=False, include_metadata=False)
    elif choice == "3":
        resume_command(session_id=None)
    elif choice == "4":
        status()
    else:
        raise typer.BadParameter(f"Unknown mode: {choice}")


if __name__ == "__main__":
    app()
