# Resume tailoring with Codex

This repository turns a comprehensive LaTeX resume into job-specific, one-page A4 resumes through a conversational Codex workflow.

[`master/_resume.tex`](master/_resume.tex) is the verified source of truth. During tailoring, Codex reviews every education item and work role, then asks you to choose which projects belong before reviewing the selected projects' bullets. It does not invent facts or silently remove content to make a resume fit.

## Repository structure

```text
cover-letter/                    Editable cover letters and rendered PDFs
master/
  _resume.tex                    Comprehensive resume source
  Morgan_Le_Resume.pdf           Generated comprehensive resume
pre-made/
  finance-consulting/            Finance and consulting resume
  forward-deployed-engineer/     Forward Deployed Engineer resume
  jake-style/                    Alternate Jake-style resume layout
  product-decision-data-science/ Product and Decision Data Science resume
  quantitative-research-finance/ Quantitative Research and Finance resume
  software-data-engineering/     Software Engineering and Data Engineering resume
.agents/skills/tailor-resume/     Repository-local Codex skill, session helper, and validator
scripts/build_resume.sh           Isolated Tectonic build script
scripts/run_resume_app.sh         One-command local web-app launcher
shared/latex/                     Shared LaTeX classes, styles, and fonts
webapp/                           Local resume workspace service and interface
AGENTS.md                         Repository rules for Codex
SPEC.md                           Detailed workflow contract
pyproject.toml and uv.lock        Validator dependencies
```

Job-specific resume folders and session data are disposable local artifacts ignored by Git. `master/_resume.tex` remains the canonical resume history; `pre-made/` contains reusable general-purpose variants.

## Cover letters

The AQR Arbitrage 2027 Research Summer Analyst letter is saved in `cover-letter/aqr-arbitrage-research-summer-analyst-2027/` as editable Markdown and a one-page PDF. It preserves the consulting template's experience narrative and adapts the opening and closing to investment research, with compact signature spacing.

The BNP Paribas 2027 Summer Analyst Internship - Corporate Functions, Operations letter is saved in `cover-letter/bnp-paribas-corporate-functions-operations-intern-2027/` as editable Markdown and a one-page PDF. It adapts the consulting template toward operations, client service, and continuous improvement, with compact signature spacing.

The West Monroe 2027 Data & Analytics Consulting Intern letter is saved in `cover-letter/west-monroe-data-analytics-consulting-intern-2027/` as editable Markdown and a one-page PDF. It follows the general consulting letter's narrative style, with content tailored to the New York role. The original consulting letter remains in `cover-letter/consulting/`.

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
3. Review every education item and work role, keeping all verified work positions represented.
4. Show all projects together and ask you to include or exclude each one.
5. Ask you to keep, rewrite, or remove every bullet in the required entries and included projects.
6. Save each message's decisions atomically under `.resume/sessions/` so an interrupted review can resume.
7. Build and validate the approved resume without changing the master source.
8. Verify that the result is exactly one A4 page and visually inspect it.

You can reply naturally, for example:

```text
Keep 1 and 3. Rewrite 2 to emphasize the forecasting work, but do not add new metrics.
```

Master updates are append-only in the interactive workflow. To add an accepted fact or bullet to the source of truth, explicitly ask Codex to do so.

### Fast session resume

The bundled session helper stores parsed entries and the master-resume hash. On a continued review, it verifies that hash and returns only the active entry. If the master is unchanged, Codex does not need to reread the complete source or repository instructions. If it changed, the helper marks the session stale so Codex can reread and reconcile safely.

When one reply decides several bullets or projects, the helper persists them together with one atomic ledger replacement. Undo reverses that complete user-message batch.

## Use the local Resume Workspace

The repository also includes a local, self-hosted browser interface. It opens with the verified master resume already loaded, then shows a complete set of AI recommendations inline across the resume for each tailoring session.

Start it from the repository:

```bash
./scripts/run_resume_app.sh
```

Open the local address printed by the launcher. The server listens only on `127.0.0.1` by default.

The visual workflow is:

1. Review the built-in master resume; no upload is required.
2. Add the company, role, and complete job description.
3. Use **Copy request for Codex** and paste it into the active Codex task. When the page is open in a compatible Codex browser, its registered workspace tools let Codex read the saved session and submit the complete suggestion set directly.
4. Review every suggestion anywhere on the full resume using **Approve suggestion**, **Keep current**, or **Other…**. Other can accept manual wording, remove the bullet, confirm a missing fact, or send a focused request back to Codex for a revised suggestion.
5. Include or exclude every project, then review bullets for included projects.
6. Build a live PDF preview. If it exceeds one page, revisit the specific fitting opportunities shown by the UI.
7. Export only after all decisions are resolved and the current preview is one A4 page.

Workspace sessions, decision history, and previews remain under `.resume/webapp/` and are ignored by Git. The master resume is read-only in the web interface. The web server does not create a hidden Codex session or require a second API key.

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
- Select projects explicitly for each tailored resume; project exclusion never removes them from the master source.
- Require explicit bullet-level decisions during tailoring and page fitting, plus explicit project-level inclusion decisions.
- Treat every tailored resume as a one-page A4 document.
- Review `master/_resume.tex` before making a fork public because it contains personal information.
- Codex does not commit or push changes unless explicitly asked.

See [`SPEC.md`](SPEC.md) for the full workflow contract.

## License

No open-source license is included. The repository may be visible and forkable on GitHub, but reuse rights remain reserved until the owner chooses a license.
