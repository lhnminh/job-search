# Conversational resume tailoring with Codex

This repository is a reusable, repository-local Codex workflow for turning one comprehensive LaTeX resume into job-specific, one-page A4 resumes. Tailoring happens in the active Codex conversation: you review every education item, role, project, and bullet before Codex writes a result.

The workflow is deliberately conservative. It treats the root `_resume.tex` as the verified source of truth, does not invent facts, and does not silently remove content to fit a page.

## What is tracked

```text
_resume.tex                                  # Comprehensive source of truth
.agents/skills/tailor-resume/                # Repository-local Codex skill
  SKILL.md
  agents/openai.yaml
  scripts/validate_resume.py
  scripts/resume_validation.py
scripts/build_resume.sh                      # Isolated Tectonic build
shared/latex/                                # Shared class, styles, and fonts
AGENTS.md                                    # Repository rules for Codex
SPEC.md                                      # Workflow contract
pyproject.toml and uv.lock                   # Validator dependency lock
```

Generated PDFs, session ledgers, and tailored result folders are local working artifacts and are ignored by Git. The root `_resume.tex` remains tracked so each fork has one canonical, reviewable history of verified resume facts.

## Prerequisites

- [Codex](https://openai.com/codex/) with repository-local skills available.
- [Tectonic](https://tectonic-typesetting.github.io/) on `PATH` for PDF builds. On macOS with Homebrew: `brew install tectonic`.
- [uv](https://docs.astral.sh/uv/) with Python 3.12 or later for deterministic validation.
- Optional: Poppler for rendering PDF pages during visual QA.

Install the validator dependency:

```bash
uv sync
```

## Set up your fork

1. Fork or clone the repository.
2. Replace the personal details and resume content in root `_resume.tex` with your own verified history. Preserve the `moderncv` document structure and `\customcventry` entries used by the validator.
3. Review `AGENTS.md` and adjust any personal content policies you want Codex to follow.
4. If desired, replace `Morgan_Le_Resume.pdf` in `scripts/build_resume.sh`, the skill, and the repository instructions with your preferred output filename.
5. Build the comprehensive reference once:

```bash
./scripts/build_resume.sh
```

The generated root PDF is ignored; `_resume.tex` is the durable source.

## Tailor a resume

Open the repository in Codex and start a task with:

```text
Use $tailor-resume to tailor my resume for this job description:

<paste the complete job description>
```

Codex will:

1. Read the complete root source and job description.
2. Propose a lowercase, hyphenated result-folder name.
3. Review the resume section by section and entry by entry, with every bullet numbered.
4. Require an explicit Keep, Rewrite, or Remove decision for each bullet.
5. Save decisions to a local `.resume/sessions/` ledger so interrupted work can resume.
6. Assemble the approved tailored source without changing root `_resume.tex`.
7. Build, validate, and visually inspect an exactly one-page A4 PDF.

Natural replies work; no terminal command language is required. For example:

```text
Keep 1 and 3. Rewrite 2 to emphasize the forecasting work, but do not add any new metrics.
```

To append an accepted fact or bullet to the source of truth, say so explicitly. Root updates are append-only in this workflow.

## Build and validate manually

With no argument, the build script compiles root `_resume.tex`:

```bash
./scripts/build_resume.sh
```

Pass a root-level result folder to build a tailored version:

```bash
./scripts/build_resume.sh "company-role"
```

The build runs in a temporary directory, copies in `shared/latex/`, and writes only `company-role/Morgan_Le_Resume.pdf`.

Validate a tailored result after building:

```bash
uv run python .agents/skills/tailor-resume/scripts/validate_resume.py "company-role"
```

The validator checks that the folder contains only its source and PDF, historical employers/titles/dates and contact fields still match the source of truth, numeric claims are verified, every work position remains represented, and the PDF is one A4 page with extractable text and hyperlinks.

Run the validator unit tests with:

```bash
uv run python -m unittest discover -v
```

## Data and Git behavior

- Root `_resume.tex` is intentionally tracked and may contain personal information. Review it carefully before making a fork public.
- Root and tailored PDFs are generated and ignored.
- Root-level tailored `_resume.tex` files are ignored, so application-specific drafts and job-search history are not published accidentally.
- `.resume/`, virtual environments, Python caches, and LaTeX intermediates are ignored.
- The skill never commits or pushes unless you explicitly request it.

## Design constraints

- Never invent employers, titles, dates, responsibilities, technologies, metrics, or outcomes.
- Do not change a historical job title merely to match a posting.
- Keep the comprehensive root source append-only during the interactive workflow.
- Preserve every verified work position with at least one substantive bullet in each tailored version.
- Require explicit line-level decisions during tailoring and page fitting.
- Require every tailored PDF to be exactly one A4 page and visually inspect it before use.

See `SPEC.md` for the full behavioral contract.

## License

No open-source license is included yet. Public visibility lets people read and fork the repository on GitHub, but reuse rights remain reserved until the repository owner chooses a license.
