---
name: tailor-resume
description: Tailor, review, and build application-specific resumes in this repository through a conversational Codex workflow. Use when the user provides a job description, asks for a targeted resume, wants to review resume content section by section or job by job, points to numbered bullets for rewriting, or asks to build and verify a tailored one-page PDF.
---

# Tailor Resume

Work directly in the current Codex conversation. Follow `AGENTS.md`; do not create another chat or call another model.

## Route reusable premade work

When the user asks to create or update a reusable variant under `pre-made/`, maintain its `resume.md` content source, compiled `_resume.tex`, and verified `Morgan_Le_Resume.pdf`. Use `scripts/md_to_latex.py` to compile `resume.md` into the desired template layout (`jake`, `vmock`, `loc`). Canonical format references live under `templates/Jake/`, `templates/Vmock/`, and `templates/Loc/`.

## Route Resume Workspace sessions

When the user refers to the local Resume Workspace, its browser UI, or a session created there, use the workspace bridge instead of creating a conversational ledger session. Prefer the page's `read_resume_tailoring_context` and `submit_resume_suggestions` WebMCP tools when they are available. Otherwise use:

```bash
uv run python webapp/manage.py sessions
uv run python webapp/manage.py context <session-id>
uv run python webapp/manage.py submit <session-id> <analysis-json-file>
uv run python webapp/manage.py revise <session-id> <request-id> <suggestion-json-file>
```

Read the complete workspace context, including pending revision requests. For an initial analysis, generate one recommendation for every bullet plus one Include or Exclude recommendation for every project. Submit that complete analysis in one validated operation so every suggestion is immediately available through the focused resume review and side panel. For a pending revision, replace only the requested suggestion with a grounded alternative. Do not make decisions for the user or invent facts. The UI persists explicit approvals, alternate wording, project choices, undo history, previews, and export state.

## Route new and resumed sessions

Use `.agents/skills/tailor-resume/scripts/session_ledger.py` for gitignored state. Its `show` and `update` commands verify the `master/_resume.tex` hash and return only the active entry.

For a known session with explicit bullet decisions, make one `update` call containing every decision from that user message. Do not call `show` first. For an interrupted session, run:

```bash
uv run python .agents/skills/tailor-resume/scripts/session_ledger.py show <session-id>
```

If it returns `ready`, continue from its active entry without rereading `AGENTS.md` or `master/_resume.tex`. Add `--include-job-description` only when the job description is no longer in conversation context. If it returns `stale`, reread the changed master and reconcile before continuing. Use `list` when the session ID is unknown.

For a new session:

1. Read `AGENTS.md`, inspect `git status`, and read the complete master resume and job description.
2. Identify new versus existing variant, state that the master stays untouched unless the user explicitly requests an append, and propose a lowercase hyphenated slug without overwriting an existing folder.
3. Save the pasted job description to a temporary gitignored file, then create the ledger:

```bash
uv run python .agents/skills/tailor-resume/scripts/session_ledger.py start <session-id> --target-slug <slug> --job-description-file <path>
```

The ledger records every source-order entry and bullet, the job description, master hash, project selections, bullet decisions, confirmed facts, and current entry. Do not review the contact header. Employer, historical title, school, and date lines are locked context.

## Review entries

Review Education and Relevant Experience first, then Projects and other sections unless the user jumps elsewhere. Every verified experience role is mandatory and must retain at least one substantive bullet. Show one complete mandatory entry at a time with all locally numbered bullets. Recommend exactly one action per bullet: Keep, Rewrite, Remove, or Ask for one missing fact. Reasons must be short and job-specific.

Use this visual hierarchy:

```markdown
### Relevant Experience — Entry 3 of 5

**Employer** · Historical title · Dates

*0 of 3 bullets decided · Suggestions are previews only.*

#### 1. Rewrite recommended

*Current wording — from source*
> Existing bullet...

**Suggested wording — not applied**
> Complete verified replacement...

*Why this helps:* Brief reason.

`1 use suggestion` · `1 keep current` · `1 revise: ...` · `1 remove`
```

Italicize secondary context, progress, questions, and reasons. Bold suggestions and accepted states. Keep resume wording in ordinary blockquotes. Never call wording merely “old” or “new,” combine current and suggested text in one block, or imply that a preview is applied. Use **Final wording — accepted for tailored version** after acceptance and **Removed — accepted for tailored version** after approved removal.

Accept natural requests such as “keep 1 and 3,” “make 2 shorter,” “use all recommendations,” Back, and Undo. Show enough surrounding context after a targeted revision. If the request did not authorize acceptance, ask before saving it. Do not advance until every bullet in a mandatory or included entry has an explicit Keep, Rewrite, or Remove decision; summarize each completed section.

## Select projects before editing them

When the review reaches Projects, run:

```bash
uv run python .agents/skills/tailor-resume/scripts/session_ledger.py projects <session-id>
```

Show every project together before showing any project bullets. Recommend exactly one job-specific action per project: Include or Exclude. Make clear that this selects the portfolio for the tailored version and does not change the master.

```markdown
### Projects — Select for this resume

*0 of 3 projects decided · The master remains unchanged.*

1. **Project name** — Include recommended
   *Why:* Direct evidence for the role's core requirement.
2. **Project name** — Exclude recommended
   *Why:* Weaker fit than the selected projects for a one-page resume.

`include 1 and 3` · `exclude 2` · `use recommendations`
```

Require an explicit Include or Exclude decision for every project. After saving all choices, review only included projects entry by entry and require a decision for each of their bullets. Do not review excluded-project bullets; the explicit Exclude decision removes the complete project only from the tailored version. The user may include all projects or none.

## Save decisions efficiently

Persist all explicit decisions from one user message in one atomic batch before replying. Each `--decision` takes `ENTRY BULLET ACTION TEXT_OR_DASH`; use `-` for Keep, Remove, or Clear. Each `--project-decision` takes `ENTRY include|exclude|clear`. One command may contain multiple flags of both kinds:

```bash
uv run python .agents/skills/tailor-resume/scripts/session_ledger.py update <session-id> \
  --decision 3 1 rewrite "Accepted wording" \
  --decision 3 2 keep - \
  --decision 3 3 remove - \
  --project-decision 8 include \
  --project-decision 9 exclude \
  --current-entry 4
```

This single atomic replacement preserves every bullet-level and project-selection decision. Add confirmed facts with repeated `--confirmed-fact` flags. Run `undo <session-id>` to revert the most recent user-message batch. Never save invented or strengthened facts.

For a routine approval in an active session, use this as the complete fast path: run exactly one `update` command, set `--current-entry` to the next review entry when the current entry becomes complete, and render the returned `current_entry` immediately. Do not call `show` before or after the update, reread repository instructions, inspect unrelated files, rerun validation, or narrate intermediate processing. Perform additional checks only when `update` reports a stale session or an error. A brief approval such as “approve,” “use it,” or “do so” refers to the pending suggestion in the active entry when only one unresolved suggestion is awaiting confirmation.

## Assemble and verify

After all mandatory entries and included projects are decided, show a compact decision summary and obtain approval to assemble. Copy the latest master into the approved target folder, remove explicitly excluded projects, and apply only accepted bullet decisions. Remove active `\newpage` commands. For an existing variant, show the final source diff before overwriting.

Build with `./scripts/build_resume.sh "<target-slug>"`, then run the bundled validator. If the PDF exceeds one page, present specific line-level fitting choices and rebuild only after explicit decisions; never shorten automatically. Finish only after one-page A4, text, hyperlink, and visual checks pass. Remove temporary QA files and the completed ledger unless the user asks to retain it. Report the result and Git state; do not commit or push unless asked.
