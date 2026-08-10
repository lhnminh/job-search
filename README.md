# Resume tailoring with Codex

This repository turns a comprehensive LaTeX resume into job-specific, one-page A4 resumes through a conversational Codex workflow.

The root [`_resume.tex`](_resume.tex) is the verified source of truth. During tailoring, Codex reviews every education item, role, project, and bullet with you before writing a result. It does not invent facts or silently remove content to make a resume fit.

## Repository structure

```text
_resume.tex                       Comprehensive resume source
.agents/skills/tailor-resume/     Repository-local Codex skill and validator
scripts/build_resume.sh           Isolated Tectonic build script
shared/latex/                     Shared LaTeX classes, styles, and fonts
AGENTS.md                         Repository rules for Codex
SPEC.md                           Detailed workflow contract
pyproject.toml and uv.lock        Validator dependencies
```

Generated PDFs, tailored resume folders, and session data are local artifacts ignored by Git. Only the root `_resume.tex` is the canonical, version-controlled resume history.

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
2. Replace the personal details and resume content in root `_resume.tex` with your verified history. Keep the existing `moderncv` structure and `\customcventry` entries used by the validator.
3. Review `AGENTS.md` and adjust the content policies if needed.
4. Build the comprehensive resume:

   ```bash
   ./scripts/build_resume.sh
   ```

The build creates `Morgan_Le_Resume.pdf` in the repository root. The PDF is ignored by Git; `_resume.tex` remains the durable source.

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
5. Save progress under `.resume/sessions/` so an interrupted review can resume.
6. Build and validate the approved resume without changing the root source.
7. Verify that the result is exactly one A4 page and visually inspect it.

You can reply naturally, for example:

```text
Keep 1 and 3. Rewrite 2 to emphasize the forecasting work, but do not add new metrics.
```

Root updates are append-only in the interactive workflow. To add an accepted fact or bullet to the source of truth, explicitly ask Codex to do so.

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
- Do not change a historical job title merely to match a job posting.
- Keep at least one substantive bullet for every verified work position in a tailored resume.
- Require explicit line-level decisions during tailoring and page fitting.
- Treat every tailored resume as a one-page A4 document.
- Review root `_resume.tex` before making a fork public because it contains personal information.
- Codex does not commit or push changes unless explicitly asked.

See [`SPEC.md`](SPEC.md) for the full workflow contract.

## License

No open-source license is included. The repository may be visible and forkable on GitHub, but reuse rights remain reserved until the owner chooses a license.
