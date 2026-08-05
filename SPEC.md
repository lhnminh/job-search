# Interactive Resume CLI Specification

## Goal

Provide a local terminal tool that feels like a focused Codex chat for creating and reviewing resume variants from this repository.

The tool has two modes:

1. **Tailor:** Create a one-page application-specific resume from a pasted job description.
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
2. Analyzes the job description and the root resume.
3. Suggests a descriptive folder slug.
4. Proposes the selected, ordered, and rewritten LaTeX resume.
5. Shows the recommendation and accepts natural-language revision instructions.
6. Requires confirmation before creating or overwriting a folder.
7. Validates the proposal against verified root facts and historical titles.
8. Runs a Codex fact-audit comparing every proposed claim with the root source and explicit user confirmations.
9. Builds the proposed version with the existing Tectonic build script.
10. Iterates on content density when necessary until the tailored PDF is exactly one A4 page.
11. Verifies page count, page size, extractable text, and hyperlinks.
12. Renders every final PDF page and asks the same read-only Codex thread to reject clipping, overlap, broken glyphs, awkward page breaks, or orphaned headings.

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

## One-page requirement

- Every tailored PDF must be exactly one A4 page.
- The root source-of-truth PDF may contain multiple pages.
- Page fitting should prefer content selection and concise writing over font-size or margin changes.
- If automatic fitting cannot produce a valid one-page PDF, the tool must report the failure instead of claiming success.

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
