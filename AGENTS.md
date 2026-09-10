# Resume Repository Instructions

## Purpose

This repository maintains one comprehensive resume reference and multiple application-specific resume versions.

Before editing, identify which of these the user is requesting:

1. A change to the comprehensive reference in `master/_resume.tex`.
2. A change to an existing tailored version.
3. A new tailored version for a job, company, or discipline.

Do not treat these as interchangeable.

## Canonical Reference: `master/_resume.tex`

`master/_resume.tex` is the canonical content library and source of truth for verified resume facts. Its rendered counterpart is `master/Morgan_Le_Resume.pdf`.

Only active, uncommented resume content is verified as the user's. Commented-out resume entries, bullets, projects, awards, skills, and examples are not the user's claims and must never be activated, proposed, or used in any resume version.

- It should accumulate all verified positions, bullet points, projects, skills, awards, and education details.
- It may be two or more pages. Do not shorten it merely to meet a one-page resume convention.
- Do not remove content from it to make a tailored application stronger.
- Preserve unrelated reference content whenever adding or updating material.
- Build new tailored versions from the latest `master/_resume.tex` unless the user explicitly names another starting point.

### Interactive Codex source rules

The repo-specific `tailor-resume` skill is the interactive workflow. It follows a stricter append-only policy for the master source of truth:

- Automated skill operations may append accepted bullets, projects, or facts to `master/_resume.tex`.
- The skill must never replace or delete existing master content.
- Tailored versions may replace or remove their own content without changing the master source.
- A tailored proposal is appended to the master only after the user explicitly selects `/source`.
- A new metric, responsibility, technology, or outcome requires explicit user confirmation before the skill may treat it as verified.
- Tailoring must happen directly in the active Codex conversation. Do not create a nested Codex chat, terminal chat interface, or require a separate API key.
- The local Resume Workspace may present that same workflow visually. Its state belongs under the gitignored `.resume/webapp/` directory, and AI suggestions must still come from the active Codex conversation through the workspace bridge or registered WebMCP tools. The web server must not start a nested model session.
- A new tailoring session must begin from a complete copy of `master/_resume.tex` and review the resume section by section, then entry by entry. Each education item and job is shown with all of its numbered bullets together, and every bullet requires an explicit decision. Before reviewing project bullets, show one complete project shortlist and require an explicit Include or Exclude decision for every project. Only included projects proceed to entry-level bullet review; excluded projects are removed from the tailored version by that project-level decision. The contact header is excluded.
- A continuing session may use the bundled ledger helper to verify the saved master hash and load only the active entry. When the hash matches, do not reread `AGENTS.md`, the full master, or a job description already present in conversation context. A mismatch makes the session stale and requires a complete master reread and reconciliation before continuing.
- Employer, historical title, and date lines are locked context in the interactive session.
- Tailoring must not automatically remove, replace, or shorten content during either initial tailoring or page fitting. Every content mutation requires an explicit bullet-level decision, except that an explicit project-level Exclude decision removes that complete project from the tailored version.
- Session state must include every explicit bullet and project-selection decision before Codex replies. When one user message decides multiple items, persist all of those decisions together in one atomic batch rather than performing separate ledger writes.

These interactive-tool rules take precedence over the default manual merge semantics below whenever the skill is applying a change.

### Default merge semantics

When the user supplies new content for the general reference, apply these defaults unless the user explicitly says otherwise:

- **Position bullet points:** Replace the active bullets for the named position with the newly supplied bullets. Do not delete the position or unrelated positions.
- **Projects:** Append new projects. Do not replace, hide, comment out, or delete existing projects.
- **Awards, skills, education, and other sections:** Append new entries or update only the explicitly named entry. Preserve unrelated entries.
- **Metrics, dates, technologies, and employer names:** Treat user-provided facts as authoritative. Do not silently weaken, normalize, or reinterpret them.
- **Layout and contact information:** Preserve them unless the user explicitly requests a layout or contact change.

If a supplied attachment contains a full LaTeX document but the user asks to use its bullets or content, merge the requested content into the current source. Do not blindly replace the entire file or reintroduce previously fixed LaTeX problems.

## Tailored Versions

Tailored versions live in folders named `<purpose>` or `<company-role>`.

Examples:

- `finance-consulting/`
- `macquarie-asset-management/`

For a new tailored version:

1. Create a descriptive internal folder.
2. Copy only the latest `master/_resume.tex` into it.
3. Select, reorder, condense, or rewrite the most relevant verified content.
4. Preserve factual accuracy and quantified outcomes.
5. Build and visually verify the tailored version, which creates its folder-owned PDF.

Tailored versions are selective snapshots. They do not replace the reference and do not automatically update existing variants unless the user asks for synchronization.

### Reusable premade formats

Reusable variants under `pre-made/<purpose>/` each contain:

- `resume.md` as the format-neutral content source.
- `_resume.tex` as the standalone compiled LaTeX source (using the default Jake layout).
- `Morgan_Le_Resume.pdf` as the built, normalized 1-page A4 PDF.

Formatting templates live under `templates/`:
- `templates/Jake/` for the standard 11pt Jake template.
- `templates/Vmock/` for the compact 10pt Jake/Vmock template.
- `templates/Loc/` for the moderncv template.

Use `scripts/md_to_latex.py` to compile `resume.md` to any template (`jake`, `vmock`, `loc`).

### Tailoring rules

- Never invent experience, investment responsibilities, metrics, dates, technologies, or outcomes.
- Never change an official historical job title merely to match a job description.
- A targeted headline or section title may be adjusted when useful, as long as it is clearly positioning rather than a claimed past role.
- Prefer evidence from the reference that directly matches the job description.
- Flag material eligibility mismatches to the user, but do not alter truthful education or employment facts to hide them.
- Every tailored version must be exactly one A4 page. This is a hard submission rule, not a per-job preference.
- Preserve every verified work position with at least one substantive bullet. Allocate additional bullets to the roles most relevant to the job description, and consolidate repeated technology lists before removing a position.
- Treat work experience as mandatory coverage and projects as a selective portfolio. Never drop a work position through the project-selection workflow.
- Resume variants created by the interactive skill must be exactly one A4 page.

## Projects Are Additive

Projects in `master/_resume.tex` are a reference inventory.

- Adding a project means placing it alongside existing projects.
- Do not infer that a newly supplied project should replace the currently visible project.
- Removing or commenting out a project requires an explicit user request.
- Page count is not a reason to delete a project from the general reference.

## Build and Output Rules

Use the existing build script:

```bash
./scripts/build_resume.sh
./scripts/build_resume.sh "resume-folder-name"
```

- No argument builds the master source of truth.
- A folder argument builds that internal version (e.g. `./scripts/build_resume.sh pre-made/finance-consulting`).
- The source-of-truth build writes `master/Morgan_Le_Resume.pdf`.
- A tailored build writes exactly `<selected-resume-folder>/Morgan_Le_Resume.pdf`.
- Every active tailored or premade resume folder contains `_resume.tex` and its independent `Morgan_Le_Resume.pdf`.
- Shared LaTeX classes, styles, and fonts belong only in `shared/latex/`.
- Do not duplicate shared support files inside resume folders.
- The build script must compile in a temporary directory containing the selected `_resume.tex` and copied `shared/latex/` files.
- Do not expose internal version names in the PDF filename.
- A build may overwrite only the master PDF or the PDF inside the selected tailored folder. It must never overwrite another version's PDF.
- Do not use a shared output PDF or a central `output/pdf/` directory.
- Tectonic is installed through Homebrew. Prefer the installed `tectonic` command.
- The build script must normalize Tectonic output to PDF 1.5 with a classic cross-reference table before publishing it, while preserving text, page geometry, and hyperlinks.
- Built resume text must not contain Unicode presentation-form ligatures such as `ﬀ`; the PDF normalizer expands their Unicode mappings for ATS compatibility without changing their visual rendering.
- The Jake-style source must use T1 encoding and Latin Modern's Type 1 fonts so legacy resume parsers do not have to interpret CID Type 0 `Identity-H` text fonts.
- Build intermediates must remain temporary and should be removed after verification.

## PDF Verification

After every resume build:

1. Confirm the PDF compiles successfully.
2. Check page count and A4 page size.
3. Render every page to PNG and inspect it visually.
4. Check for clipped text, overlap, broken glyphs, awkward page breaks, and orphaned headings.
5. Confirm important content is text-extractable for ATS use.
6. Confirm hyperlinks remain present.
7. Remove temporary QA files before completing the task.

For the master source of truth, multiple pages are acceptable. Use clean page boundaries rather than deleting content. Every tailored version must remain exactly one A4 page.

## Editing Workflow

Follow this sequence and explain changes step by step:

1. Read this file and inspect `git status`.
2. Identify whether the target is the general reference, an existing variant, or a new variant.
3. Read all supplied attachments completely.
4. State the intended replace-versus-append behavior before editing.
5. Preserve unrelated user changes and resume content.
6. Edit the appropriate `_resume.tex` source, not the generated PDF.
7. Build the requested version.
8. Perform PDF and content verification.
9. Update `README.md` when adding a durable new workflow or named variant.
10. Report what changed, what remained untouched, and whether changes are committed or pushed.

## Git and Python

- Do not commit or push changes unless the user explicitly requests it.
- Do not stage unrelated worktree changes.
- Keep `.venv/`, caches, LaTeX intermediates, and temporary renders untracked.
- The validator uses uv with Python 3.12. Keep `pyproject.toml`, `.python-version`, and `uv.lock` tracked when its dependencies change.
- Interactive skill sessions belong under the gitignored `.resume/sessions/` directory.
- Use `uv run python -m unittest discover -v` for the validator test suite.
- Use the repo-specific `$tailor-resume` skill for the primary conversational workflow. After building, run `uv run python .agents/skills/tailor-resume/scripts/validate_resume.py "<target-folder>"` before visual PDF QA.
- Start the local Resume Workspace with `./scripts/run_resume_app.sh`. It must bind to a loopback address by default and preserve the same master-source, explicit-decision, one-page, validation, and visual-QA rules as the conversational workflow.
