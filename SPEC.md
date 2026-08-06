# Conversational Resume Skill Specification

## Goal

Provide a repo-specific Codex skill that creates and reviews resume variants directly in the active Codex conversation. Do not recreate Codex chat through a nested Python application.

The workflow supports two intents:

1. **Tailor:** Create a polished one-page application-specific resume from a pasted job description.
2. **Review:** Walk through a resume section by section, entry by entry, and bullet by bullet with conversational Codex feedback.

The repo-specific skill lives at `.agents/skills/tailor-resume/`. It is the only interactive interface; the Python code under the skill is deterministic validation support, not a chat application.

## Canonical content

- The repository root `_resume.tex` remains the comprehensive source of truth.
- Automated interactive operations may only append explicitly accepted content to the root source.
- The skill must never replace or delete an existing root bullet, entry, project, section, or verified fact.
- Tailored versions may select, reorder, condense, replace, or remove content without changing the root source.
- An accepted tailored bullet reaches the root source only through an explicit `/source` action.

## Facts and claims

- Codex may rewrite verified facts already present in the source of truth.
- Codex may ask the user for an additional fact or metric.
- A new fact becomes verified only after the user explicitly supplies or confirms it.
- Codex must not independently invent employers, titles, dates, responsibilities, technologies, metrics, or outcomes.
- Historical company names and job titles must remain unchanged.

## Tailor workflow

The user invokes `$tailor-resume` and pastes a job description in the Codex conversation. The skill then:

1. Uses the active repository-aware Codex conversation; it does not start a nested Codex thread.
2. Reads the complete root resume and job description without changing the source.
3. Creates a gitignored decision ledger for resumability.
4. Walks through the resume section by section and entry by entry: each education item, job, and project is shown with all of its numbered bullets and Codex recommendations together. The contact header is excluded, while entry headers are locked context.
5. Lets the user point to a specific bullet within the visible entry using natural language, such as “rewrite line 2 with more finance emphasis,” without losing the surrounding job context.
6. Requires an explicit decision for every bullet before moving to the next entry. The user may accept, keep, remove, regenerate, rework, accept all, keep all, go back, undo, or quit.
7. Saves every decision immediately so the session can resume at the same entry.
8. Suggests a descriptive folder slug and requires confirmation before creating or overwriting a folder.
9. Builds temporary previews only after every entry has been reviewed.
10. If the draft exceeds one page, enters an interactive page-fit pass. It presents low-relevance or metadata lines one at a time and requires the user to keep, remove, or approve a shorter rewrite. The tool never deletes or rewrites a line automatically.
11. Runs the deterministic validator against verified root facts, historical titles, PDF structure, and the one-substantive-bullet minimum for every work position.
12. Audits every proposed claim against the root source and explicit user confirmations.
13. Shows a final diff and requires confirmation before writing the tailored folder.
14. Builds and verifies exactly one A4 page, extractable text, and hyperlinks.
15. Renders the final PDF and visually rejects clipping, overlap, broken glyphs, awkward page breaks, or orphaned headings.

There is no non-interactive acceptance shortcut because it would bypass the required entry review and bullet decisions.

## Review workflow

The user selects the root source or an existing tailored version and may optionally paste a job description. The tool then:

1. Parses sections, entries, and bullets from `_resume.tex`.
2. Presents one complete entry at a time with numbered bullets, assessments, and suggested wording.
3. Accepts natural-language instructions targeting one or several numbered bullets, plus requests to keep all, accept all, go back, undo, or revisit a section.
4. Requires an explicit decision for every bullet and summarizes each section before moving on.
5. Shows a final diff and requests confirmation before saving.
6. Builds and verifies the selected resume after saving.

For root review, accepting revised wording appends it beside the existing bullet; it never replaces the original. For tailored review, acceptance replaces only the selected tailored bullet. Root insertion always requires an explicit source-of-truth request.

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
- A skill session ledger records the target, root hash, job description, current section and entry, accepted bullet decisions, and confirmed facts.
- The active Codex task and ledger provide conversational continuity.
- Completed skill ledgers are removed after successful verification unless the user requests retention.

## Authentication and model selection

- The skill runs in the user's active Codex session and uses its existing authentication and configured model.
- No OpenAI API key, local Codex SDK wrapper, or nested model call is required.

## Safety boundaries

- Codex preserves the source during analysis and applies only explicitly accepted edits with repository tools.
- PDF page images are temporary, used only for visual QA, and deleted immediately afterward.
- Folder paths and slugs must remain inside the repository.
- Existing tailored folders require explicit overwrite confirmation.
- The bundled validator checks LaTeX structure, historical titles, numeric claims, one-page A4 output, text extraction, and hyperlinks.
- The skill never commits or pushes Git changes without an explicit request.

## Invocation

```text
Use $tailor-resume to tailor my resume for this job description:

<job description>
```
