---
name: tailor-resume
description: Tailor, review, and build a verified one-page resume for a supplied job description, or review resume entries and numbered bullets in this repository.
---

# Tailor Resume

Use the active assistant conversation. Read `AGENTS.md` and, when present, the gitignored `.resume/preferences.md`. Do not require a particular model, provider, skill loader, or another model session. Instructions can be loaded by path when automatic skill discovery is unavailable.

## Sources and decisions

- Verified facts come only from active, uncommented `master/resume.md` content and explicit user confirmations. Read the complete job description and master before starting.
- Select an available `pre-made/<track>/resume.md` baseline when useful; otherwise use the master. Never invent a baseline or browse `applications/` for references.
- Create the new tailored Markdown in `applications/<company-role>/resume.md`. Read an existing application only when the user explicitly selects it for updates.
- Preserve employers, official titles, dates, contact details, and verified outcomes. Keep every work position with at least one substantive bullet; prefer more coverage for relevant roles. A technologies line is not substantive coverage.
- Prioritize verified cross-functional collaboration, team leadership, and quantified revenue or business impact when allocating resume space. Trim additional projects and secondary technical details before removing these proof points; keep substantive coverage for every work position.
- Select projects and coursework from the actual applicant's verified inventory. Never assume the public example's employers, education, projects, skills, or metrics belong to the applicant.
- Follow the applicant's baseline and local layout preferences. Default to Jake, exactly one A4 page. Condense repetition before reducing substantive experience; Vmock is unavailable.
- Tailored edits do not change the master. Append accepted facts to the master only on an explicit source-of-truth request; never replace or delete master content automatically.

## Default: tailor, build, and review

1. Explain the selected baseline and intended changes before writing. Tailor only from verified material; ask for confirmation of any new fact.
2. Save the tailored Markdown and immediately build and validate. If using a baseline, run:
   ```bash
   uv run python scripts/prepare_application.py applications/<company-role> --base pre-made/<track>
   ```
   Use `--base master/resume.md` when no premade exists. Alternatively run the converter with `--template jake --build` and the validator below.
3. Run `uv run python .agents/skills/tailor-resume/scripts/validate_resume.py applications/<company-role>` before visual QA. Inspect the rendered page for clipping, overlap, glyphs, and awkward wraps. Automated checks do not substitute for visual inspection. Never present a failed or stale build as verified.
4. Present the verified PDF alongside the complete, unabbreviated Markdown diff against the saved baseline, including unchanged context. Explain the job-specific emphasis briefly. Resolve page overflow using verified wording and rebuild after each requested tweak.
5. Read the output filename from `.resume/settings.json` when present; defaults are `Resume.pdf` and `Cover_Letter.pdf`. Respect an explicit request to defer building or provide Markdown only.

## Optional entry-by-entry review

Use `.agents/skills/tailor-resume/scripts/session_ledger.py` when the user requests detailed review. Persist explicit bullet/project decisions in atomic batches; employer, historical title, and date lines remain locked. Retain all jobs while selecting projects.

## Assistants without local tools

Read `docs/PORTABLE_WORKFLOW.md`. Ask the user to supply the active master, selected baseline, and job description. Return complete Markdown and the full diff in chat so the user can save and build locally. Report PDF verification as pending until the build and visual checks actually occur. No JSON handoff or separate application is required.
