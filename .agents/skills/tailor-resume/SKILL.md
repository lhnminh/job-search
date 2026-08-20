---
name: tailor-resume
description: Tailor, review, and build application-specific resumes in this repository through a conversational Codex workflow. Use when the user provides a job description, asks for a targeted resume, wants to review resume content section by section or job by job, points to numbered bullets for rewriting, or asks to build and verify a tailored one-page PDF.
---

# Tailor Resume

Work directly in the current Codex conversation. Follow `AGENTS.md`; do not create another chat or call another model.

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

The ledger records every source-order entry and bullet, the job description, master hash, decisions, confirmed facts, and current entry. Do not review the contact header. Employer, historical title, school, and date lines are locked context.

## Review entries

Review Education, Relevant Experience, Projects, then other sections unless the user jumps elsewhere. Show one complete entry at a time with all locally numbered bullets. Recommend exactly one action per bullet: Keep, Rewrite, Remove, or Ask for one missing fact. Reasons must be short and job-specific.

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

Accept natural requests such as “keep 1 and 3,” “make 2 shorter,” “use all recommendations,” Back, and Undo. Show enough surrounding context after a targeted revision. If the request did not authorize acceptance, ask before saving it. Do not advance until every bullet in the entry has an explicit Keep, Rewrite, or Remove decision; summarize each completed section.

## Save decisions efficiently

Persist all explicit decisions from one user message in one atomic batch before replying. Each `--decision` takes `ENTRY BULLET ACTION TEXT_OR_DASH`; use `-` for Keep, Remove, or Clear. One command may contain multiple `--decision` flags:

```bash
uv run python .agents/skills/tailor-resume/scripts/session_ledger.py update <session-id> \
  --decision 3 1 rewrite "Accepted wording" \
  --decision 3 2 keep - \
  --decision 3 3 remove - \
  --current-entry 4
```

This single atomic replacement preserves every bullet-level decision. Add confirmed facts with repeated `--confirmed-fact` flags. Run `undo <session-id>` to revert the most recent user-message batch. Never save invented or strengthened facts.

## Assemble and verify

After all entries are decided, show a compact decision summary and obtain approval to assemble. Copy the latest master into the approved target folder and apply only accepted decisions. Remove active `\newpage` commands. For an existing variant, show the final source diff before overwriting.

Build with `./scripts/build_resume.sh "<target-slug>"`, then run the bundled validator. If the PDF exceeds one page, present specific line-level fitting choices and rebuild only after explicit decisions; never shorten automatically. Finish only after one-page A4, text, hyperlink, and visual checks pass. Remove temporary QA files and the completed ledger unless the user asks to retain it. Report the result and Git state; do not commit or push unless asked.
