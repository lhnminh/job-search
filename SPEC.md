# Interactive Resume CLI Specification

## Goal

Provide a local terminal tool that feels like a focused Codex chat for creating and reviewing resume variants from this repository.

The tool has two modes:

1. **Tailor:** Create a polished one-page application-specific resume from a pasted job description.
2. **Review:** Walk through a resume section by section and bullet by bullet with conversational Codex feedback.

## Canonical content

- The repository root `_resume.tex` remains the comprehensive source of truth.
- Automated CLI operations may only append accepted content to the root source.
- The CLI must never replace or delete an existing root bullet, entry, project, section, or verified fact.
- Tailored versions may select, reorder, condense, replace, or remove content without changing the root source.
- An accepted tailored bullet reaches the root source only through an explicit `/source` action.

## Facts and claims

- Codex may rewrite verified facts already present in the source of truth.
- Codex may ask the user for an additional fact or metric.
- A new fact becomes verified only after the user explicitly supplies or confirms it.
- Codex must not independently invent employers, titles, dates, responsibilities, technologies, metrics, or outcomes.
- Historical company names and job titles must remain unchanged.

## Tailor mode

The user pastes a job description as terminal text. The tool then:

1. Starts a repository-aware Codex thread in a read-only sandbox.
2. Creates a compact working copy of the complete root resume without changing its content facts, contact header, employer names, historical titles, or dates.
3. Sends all content lines to Codex in one batch so the initial analysis does not require one model request per line.
4. Walks through every education, experience, project, and technology/tool bullet individually. The contact header is excluded, while entry headers are shown as locked context.
5. Requires an explicit decision for every line: accept the displayed recommendation, keep, remove, regenerate, go back, undo, quit, or provide a natural-language instruction.
6. Saves every decision immediately so the session can resume at the same line.
7. Suggests a descriptive folder slug and requires confirmation before creating or overwriting a folder.
8. Builds temporary previews only after every line has been reviewed.
9. If the draft exceeds one page, enters an interactive page-fit pass. It presents low-relevance or metadata lines one at a time and requires the user to keep, remove, or approve a shorter rewrite. The tool never deletes or rewrites a line automatically.
10. Validates the completed proposal against verified root facts, historical titles, and the one-substantive-bullet minimum for every work position.
11. Runs a Codex fact-audit comparing every proposed claim with the root source and explicit user confirmations.
12. Shows a final diff and requires confirmation before writing the tailored folder.
13. Builds and verifies exactly one A4 page, extractable text, and hyperlinks.
14. Renders the final PDF and asks the same read-only Codex thread to reject clipping, overlap, broken glyphs, awkward page breaks, or orphaned headings.

The `--yes` shortcut is intentionally unsupported in Tailor mode because it would bypass the required line decisions.

## Review mode

The user selects the root source or an existing tailored version and may optionally paste a job description. The tool then:

1. Parses sections, entries, and bullets from `_resume.tex`.
2. Presents one bullet at a time with Codex's assessment and suggested wording.
3. Accepts natural-language instructions as well as shortcuts:
   - `/accept` - accept the current proposal.
   - `/keep` - keep the original bullet.
   - `/regenerate` - request a different proposal.
   - `/source` - accept the proposal and append it to the root source.
   - `/skip` - move on without a change.
   - `/back` - revisit the previous bullet.
   - `/undo` - undo the most recent accepted edit.
   - `/done` - finish the review.
4. Performs a section-level assessment after the bullets in each section.
5. Shows a final diff and requests confirmation before saving.
6. Builds and verifies the selected resume after saving.

For root review, `/accept` appends the proposal beside the existing bullet. It never replaces the original. For tailored review, `/accept` replaces the current tailored bullet. `/source` additionally queues the accepted wording for append-only insertion into the matching root entry.

## Page and content requirements

- Every generated tailored PDF must be exactly one A4 page.
- Every verified work position must remain present.
- Each position must retain at least one substantive bullet; technology/tool bullets do not count toward this minimum.
- Additional bullets should be allocated to the positions most relevant to the job description.
- Repeated technology lists should be consolidated into the skills section before substantive experience is removed.
- Projects may be selected and condensed after every work position is represented.
- The root source-of-truth PDF may contain multiple pages.
- Page fitting should prefer concise writing and removal of repetition over illegibly small text or extreme margins.
- Page fitting must never remove or rewrite content automatically.
- If the user's accepted fitting decisions cannot produce a valid one-page PDF without violating the content floor, the tool must report the failure instead of claiming success.

## Sessions

- Interactive state is stored under `.resume/sessions/`, which is gitignored.
- A session records its Codex thread ID, mode, target, job description, current bullet, accepted decisions, working LaTeX, and undo history.
- `resume resume` continues the most recently updated unfinished session.
- Completed sessions are marked complete and may be cleaned up later.

## Authentication and model selection

- The tool uses the local Python Codex SDK and the user's configured Codex authentication.
- Local ChatGPT sign-in is supported; an OpenAI API key is not required for personal interactive use.
- The tool uses Codex's configured default model unless the user explicitly overrides it.
- Authentication is checked before starting an AI-backed workflow.

## Safety boundaries

- Codex runs read-only during analysis and drafting.
- The Python controller, not Codex, applies accepted file changes.
- PDF page images are temporary, used only for visual QA, and deleted immediately afterward.
- Folder paths and slugs must remain inside the repository.
- Existing tailored folders require explicit overwrite confirmation.
- The controller validates LaTeX structure, historical titles, and numeric claims before writing.
- The CLI never commits or pushes Git changes.

## Commands

```bash
uv run resume
uv run resume tailor
uv run resume review
uv run resume resume
uv run resume status
```

Running `uv run resume` opens the mode-selection menu.
