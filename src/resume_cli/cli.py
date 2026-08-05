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

from .build import BuildError, BuildResult, PdfReport, build_resume, render_pdf
from .codex_backend import CodexBackendError, CodexConversation, authentication_status
from .resume import (
    ResumeDocument,
    append_bullet,
    append_bullet_by_title,
    parse_resume,
    remove_bullet,
    replace_bullet,
    resume_path,
    slugify,
    source_hash,
    tex_to_text,
    validate_slug,
    validate_root_append_only,
    validate_tailored_tex,
)
from .schemas import (
    BULLET_REVIEW_SCHEMA,
    FACT_AUDIT_SCHEMA,
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
- Optimize content selection and wording for exactly one A4 page.
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

Preserve historical titles and verified facts. Preserve the existing \\firstname, \\familyname, \\mobile, \\email, \\github, and \\linkedin lines verbatim. Preserve the existing font size, margins, contact information, and overall style. Prefer removing lower-relevance content and tightening wording. Return the full revised LaTeX in source_tex and the required structured fields.
"""


def _confirmed_facts(session: Session) -> list[str]:
    return list(session.payload.get("confirmed_facts", []))


def _validate_proposal(root_source: str, proposal: dict[str, Any], session: Session) -> list[str]:
    source_tex = proposal.get("source_tex")
    if not isinstance(source_tex, str) or not source_tex.strip():
        return ["Codex did not return LaTeX source"]
    return validate_tailored_tex(root_source, source_tex, _confirmed_facts(session))


def _visual_pdf_qa(chat: CodexConversation, report: PdfReport) -> dict[str, Any]:
    qa_parent = REPO_ROOT / "tmp" / "pdfs"
    qa_parent.mkdir(parents=True, exist_ok=True)
    qa_directory = Path(tempfile.mkdtemp(prefix="resume-cli-", dir=qa_parent))
    try:
        images = render_pdf(report.path, qa_directory)
        if len(images) != report.pages:
            raise BuildError(
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
                except BuildError as exc:
                    last_issue = str(exc)
                else:
                    return result
            else:
                last_issue = f"The generated PDF has {result.report.pages} pages; it must have exactly one."
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


def _run_tailor_session(session: Session, *, requested_slug: str | None = None, assume_yes: bool = False) -> None:
    store = SessionStore(REPO_ROOT)
    root_source = (REPO_ROOT / "_resume.tex").read_text(encoding="utf-8")
    with CodexConversation(REPO_ROOT, session.thread_id) as chat:
        session.thread_id = chat.thread_id
        store.save(session)
        if session.payload.get("phase") == "building" and session.target and session.working_tex:
            console.print(f"Continuing the build for [bold]{session.target}[/bold].")
            _complete_tailor_build(session, chat, root_source, assume_yes=assume_yes)
            return
        proposal = session.payload.get("proposal")
        if not proposal:
            with console.status("Codex is analyzing the job and source resume..."):
                proposal = chat.run_json(_tailor_prompt(session.job_description), TAILOR_SCHEMA)
        proposal = _answer_proposal_questions(chat, proposal, session, assume_yes)
        session.payload["proposal"] = proposal
        store.save(session)

        while True:
            _show_tailor_proposal(proposal)
            errors = _validate_proposal(root_source, proposal, session)
            if errors:
                console.print("[red]Proposal validation failed:[/red]")
                for error in errors:
                    console.print(f"  • {error}")
                with console.status("Codex is repairing the validation issues..."):
                    proposal = chat.run_json(
                        "Revise the full proposal to resolve these validation errors without inventing facts:\n- "
                        + "\n- ".join(errors),
                        TAILOR_SCHEMA,
                    )
                proposal = _answer_proposal_questions(chat, proposal, session, assume_yes)
                session.payload["proposal"] = proposal
                store.save(session)
                continue
            if assume_yes:
                answer = "/accept"
            else:
                answer = console.input(
                    "[bold]You[/bold] ([cyan]/accept[/cyan], [cyan]/quit[/cyan], or revision instruction): "
                ).strip()
            if answer.casefold() in {"/quit", "quit", "q"}:
                console.print(f"Session saved as [bold]{session.id}[/bold].")
                return
            if answer.casefold() not in {"/accept", "accept", "yes", "y"}:
                if not answer:
                    continue
                session.payload.setdefault("confirmed_facts", []).append(answer)
                with console.status("Codex is revising the proposal..."):
                    proposal = chat.run_json(_revision_prompt(answer), TAILOR_SCHEMA)
                proposal = _answer_proposal_questions(chat, proposal, session, assume_yes)
                session.payload["proposal"] = proposal
                store.save(session)
                continue
            audit_errors = _factual_audit(chat, proposal["source_tex"], _confirmed_facts(session))
            if audit_errors:
                console.print("[red]Factual audit failed:[/red]")
                for error in audit_errors:
                    console.print(f"  • {error}")
                with console.status("Codex is removing unsupported claims..."):
                    proposal = chat.run_json(
                        "Revise the full proposal to remove or correct these unsupported claims:\n- "
                        + "\n- ".join(audit_errors),
                        TAILOR_SCHEMA,
                    )
                session.payload["proposal"] = proposal
                store.save(session)
                continue
            break

        target, _ = _choose_slug(proposal, requested_slug, assume_yes)
        folder = REPO_ROOT / target
        source_path = folder / "_resume.tex"
        previous = source_path.read_text(encoding="utf-8") if source_path.exists() else ""
        session.target = target
        session.working_tex = proposal["source_tex"]
        session.original_hash = source_hash(previous)
        session.payload["original_tex"] = previous
        session.payload["phase"] = "building"
        store.save(session)
        _complete_tailor_build(session, chat, root_source, assume_yes=assume_yes)


@app.command()
def tailor(
    job_text: str | None = typer.Option(None, "--job-text", help="Job description text; otherwise paste interactively."),
    slug: str | None = typer.Option(None, help="Preferred output folder slug."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Accept the first fact-complete proposal non-interactively."),
) -> None:
    """Create a one-page tailored resume from a pasted job description."""
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
