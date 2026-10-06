# Chat-based resume workflow specification

## Goal

Provide an assistant-neutral chat workflow for verified, application-specific resumes and cover letters. The active assistant proposes wording, explains changes, and uses deterministic local tools to validate and build. No web application, HTTP server, browser interface, suggestion bridge, nested model call, or provider credentials are part of the workflow.

## Sources and privacy

`master/resume.md` is the private canonical source. Only active, uncommented content and explicitly confirmed facts are verified. `pre-made/` holds optional private baselines; `applications/` holds generated outputs and is never a reference catalog. Public sample facts must not be attributed to a new applicant.

Automated master updates are append-only and require an explicit source-of-truth request. Preserve employers, historical titles, dates, contacts, and verified outcomes. Every work position retains at least one substantive bullet; technologies do not count. Prefer more coverage where relevant and practical.

## Portable entry points

Explicitly load `AGENTS.md`, optional `.resume/preferences.md`, and the applicable skill file by path. Automatic skill discovery is optional. An assistant with local file and shell access can run the entire workflow. An assistant without local access can return Markdown and a complete diff in chat; the user saves and builds locally. See `docs/PORTABLE_WORKFLOW.md`.

The optional `.agents/skills/tailor-resume/scripts/session_ledger.py` persists decisions for detailed entry-by-entry chat review. It tracks the master hash, explicit choices, and undoable atomic decision batches. A changed master requires reconciliation.

## Default tailoring and review

Read the complete job description and active master, choose a premade baseline when available, and explain intended changes. Select and rewrite only verified content into the targeted Markdown. Build and validate immediately unless the user explicitly defers building. Present the current PDF with the full unabbreviated diff and concise rationale. Rebuild after requested tweaks.

The assistant must not invent facts, independently accept suggestions during detailed review, publish applications, or overwrite unrelated versions. Existing-output replacement requires authorization. Requested updates to an explicitly selected application may read only that target.

## Output

Use Jake for tailored resumes, exactly one A4 page for each resume and letter, and Markdown as the editable source. Outputs belong to `applications/<company-role>/` with `resume.md`, `_resume.tex`, and the configured resume PDF; optional letters have equivalent files. The Markdown master is never compiled.

Defaults are `Resume.pdf` and `Cover_Letter.pdf`. Private `.resume/settings.json` configures filenames; `.resume/preferences.md` holds applicant-specific writing and formatting preferences. New clones must not inherit another applicant's private settings.

Builders compile temporarily, normalize to PDF 1.5 with classic cross-references, preserve extractable text and links, and reject invalid final PDFs before replacing previous output. `scripts/prepare_application.py` stages builds, produces full diffs and review images, and publishes outputs only after checks pass. Visual inspection is required before describing layout as verified.

## Setup and tests

Use Python 3.12+, uv, Bash, Tectonic, and Poppler. Windows users need a compatible Linux environment such as WSL for Bash builds. `scripts/init_workspace.py` initializes from supplied Markdown or an explicit public demo and refuses to overwrite existing master content. `scripts/doctor.py` reports dependencies without installing them.

Tests use public or fictional fixtures and need no private master or model account. Real PDF integration tests are opt-in. Keep caches, local settings, session state, and temporary renders untracked. Never commit or push without explicit user authorization.
