# Resume Repository Instructions

## Purpose

This repository maintains one comprehensive resume reference and multiple application-specific resume versions.

Before editing, identify which of these the user is requesting:

1. A change to the comprehensive reference in the repository root `_resume.tex`.
2. A change to an existing tailored version.
3. A new tailored version for a job, company, or discipline.

Do not treat these as interchangeable.

## Canonical Reference: Root `_resume.tex`

The repository root `_resume.tex` is the canonical content library and source of truth for verified resume facts. Its rendered counterpart is the root `Morgan_Le_Resume.pdf`.

- It should accumulate all verified positions, bullet points, projects, skills, awards, and education details.
- It may be two or more pages. Do not shorten it merely to meet a one-page resume convention.
- Do not remove content from it to make a tailored application stronger.
- Preserve unrelated reference content whenever adding or updating material.
- Build new tailored versions from the latest root `_resume.tex` unless the user explicitly names another starting point.

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
2. Copy only the latest root `_resume.tex` into it.
3. Select, reorder, condense, or rewrite the most relevant verified content.
4. Preserve factual accuracy and quantified outcomes.
5. Build and visually verify the tailored version, which creates its folder-owned PDF.

Tailored versions are selective snapshots. They do not replace the reference and do not automatically update existing variants unless the user asks for synchronization.

### Tailoring rules

- Never invent experience, investment responsibilities, metrics, dates, technologies, or outcomes.
- Never change an official historical job title merely to match a job description.
- A targeted headline or section title may be adjusted when useful, as long as it is clearly positioning rather than a claimed past role.
- Prefer evidence from the reference that directly matches the job description.
- Flag material eligibility mismatches to the user, but do not alter truthful education or employment facts to hide them.
- A tailored version may be one page when appropriate, but only the tailored version should be optimized for submission length.

## Projects Are Additive

Projects in the root `_resume.tex` are a reference inventory.

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

- No argument builds the root source of truth.
- A folder argument builds that internal version.
- The source-of-truth build writes root `Morgan_Le_Resume.pdf`.
- A tailored build writes exactly `<selected-resume-folder>/Morgan_Le_Resume.pdf`.
- Every tailored resume folder must contain only `_resume.tex` and its independent `Morgan_Le_Resume.pdf`.
- Shared LaTeX classes, styles, and fonts belong only in `shared/latex/`.
- Do not duplicate shared support files inside resume folders.
- The build script must compile in a temporary directory containing the selected `_resume.tex` and copied `shared/latex/` files.
- Do not expose internal version names in the PDF filename.
- A build may overwrite only the root PDF or the PDF inside the selected tailored folder. It must never overwrite another version's PDF.
- Do not use a shared output PDF or a central `output/pdf/` directory.
- Tectonic is installed through Homebrew. Prefer the installed `tectonic` command.
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

For the root source of truth, multiple pages are acceptable. Use clean page boundaries rather than deleting content. For tailored versions, optimize page count only when appropriate to the application or explicitly requested.

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
- The project uses uv with Python 3.12. Keep `pyproject.toml`, `.python-version`, and `uv.lock` tracked when Python tooling is used.
