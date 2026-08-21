# Resume tailoring with Codex

This repository turns a comprehensive LaTeX resume into job-specific, one-page A4 resumes through a conversational Codex workflow.

[`master/_resume.tex`](master/_resume.tex) is the verified source of truth. During tailoring, Codex reviews every education item, role, project, and bullet with you before writing a result. It does not invent facts or silently remove content to make a resume fit.

## Repository structure

```text
master/
  _resume.tex                    Comprehensive resume source
  Morgan_Le_Resume.pdf           Generated comprehensive resume
product-decision-data-science/   Product and Decision Data Science variant
quantitative-research-finance/   Quantitative Research and Finance variant
.agents/skills/tailor-resume/     Repository-local Codex skill, session helper, and validator
scripts/build_resume.sh           Isolated Tectonic build script
shared/latex/                     Shared LaTeX classes, styles, and fonts
AGENTS.md                         Repository rules for Codex
SPEC.md                           Detailed workflow contract
pyproject.toml and uv.lock        Validator dependencies
```

Generated PDFs, tailored resume folders, and session data are local artifacts ignored by Git. Only `master/_resume.tex` is the canonical, version-controlled resume history.

## Requirements

- [Codex](https://openai.com/codex/) with repository-local skill support
- [Tectonic](https://tectonic-typesetting.github.io/) on `PATH`
- [uv](https://docs.astral.sh/uv/) with Python 3.12 or later
- Optional: Poppler for rendering PDFs during visual review

On macOS, install Tectonic with Homebrew:

```bash
brew install tectonic
```

Install the validator dependencies:

```bash
uv sync
```

## Set up your resume

1. Fork or clone this repository.
2. Replace the personal details and resume content in `master/_resume.tex` with your verified history. Keep the existing `moderncv` structure and `\customcventry` entries used by the validator.
3. Review `AGENTS.md` and adjust the content policies if needed.
4. Build the comprehensive resume:

   ```bash
   ./scripts/build_resume.sh
   ```

The build creates `master/Morgan_Le_Resume.pdf`. The PDF is ignored by Git; `master/_resume.tex` remains the durable source.

To use a different output filename, update it consistently in the build script, skill, and repository instructions.

## Tailor for a job

Open the repository in Codex and start a task with:

```text
Use $tailor-resume to tailor my resume for this job description:

<paste the complete job description>
```

Codex will:

1. Read the complete source resume and job description.
2. Propose a lowercase, hyphenated folder name.
3. Review each resume section, entry, and numbered bullet.
4. Ask you to keep, rewrite, or remove every bullet.
5. Save each message's decisions atomically under `.resume/sessions/` so an interrupted review can resume.
6. Build and validate the approved resume without changing the master source.
7. Verify that the result is exactly one A4 page and visually inspect it.

You can reply naturally, for example:

```text
Keep 1 and 3. Rewrite 2 to emphasize the forecasting work, but do not add new metrics.
```

Master updates are append-only in the interactive workflow. To add an accepted fact or bullet to the source of truth, explicitly ask Codex to do so.

### Fast session resume

The bundled session helper stores parsed entries and the master-resume hash. On a continued review, it verifies that hash and returns only the active entry. If the master is unchanged, Codex does not need to reread the complete source or repository instructions. If it changed, the helper marks the session stale so Codex can reread and reconcile safely.

When one reply decides several bullets, the helper persists them together with one atomic ledger replacement. Undo reverses that complete user-message batch.

## Build and validate manually

Build the comprehensive resume:

```bash
./scripts/build_resume.sh
```

Build a tailored resume from a root-level folder:

```bash
./scripts/build_resume.sh "company-role"
```

This writes only `company-role/Morgan_Le_Resume.pdf`. Validate it with:

```bash
uv run python .agents/skills/tailor-resume/scripts/validate_resume.py "company-role"
```

Run the validator tests with:

```bash
uv run python -m unittest discover -v
```

The validator checks folder contents, protected historical and contact fields, numeric claims, work-position coverage, page size and count, extractable text, and hyperlinks.

## Safety and privacy

- Never invent employers, titles, dates, responsibilities, technologies, metrics, or outcomes.
- Treat only active, uncommented master-resume content as verified; never use commented-out resume items.
- Do not change a historical job title merely to match a job posting.
- Keep at least one substantive bullet for every verified work position in a tailored resume.
- Require explicit line-level decisions during tailoring and page fitting.
- Treat every tailored resume as a one-page A4 document.
- Review `master/_resume.tex` before making a fork public because it contains personal information.
- Codex does not commit or push changes unless explicitly asked.

See [`SPEC.md`](SPEC.md) for the full workflow contract.

## License

No open-source license is included. The repository may be visible and forkable on GitHub, but reuse rights remain reserved until the owner chooses a license.
