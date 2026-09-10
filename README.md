# Resume tailoring with Codex

This repository turns a comprehensive LaTeX resume into job-specific, one-page A4 resumes through either a conversational Codex workflow or the included local Resume Workspace web app.

[`master/resume.md`](master/resume.md) is the verified source of truth in format-neutral Markdown. During tailoring, Codex reviews every education item and work role, then asks you to choose which projects belong before reviewing the selected projects' bullets. It does not invent facts or silently remove content to make a resume fit.

### Repository structure

```text
applications/                   Tailored job applications (e.g. applications/<company-role>/)
  <company-role>/
    resume.md                   Tailored Markdown resume
    cover_letter.md             Optional tailored cover letter
    Morgan_Le_Resume.pdf        Compiled 1-page A4 PDF
master/
  resume.md                     Canonical Markdown resume (source of truth)
pre-made/
  <purpose>/
    resume.md                   Curated format-neutral resume content
    cover_letter.md             Base cover letter template for this domain track
    _resume.tex                 Standalone compiled Jake LaTeX source
    Morgan_Le_Resume.pdf        Built 1-page A4 PDF
templates/
  Jake/                         Canonical original Jake source template (11pt)
  Vmock/                        Compact 10pt Jake/Vmock source template
  Loc/                          Canonical moderncv source template
.agents/skills/tailor-resume/   Repository-local skill, session helper, and validator
scripts/build_resume.sh         Isolated Tectonic and PDF-compatibility build script
scripts/md_to_latex.py          Markdown-to-LaTeX compiler for Jake, Vmock, and Loc
scripts/diff_resume.py          Structured CLI diff viewer for comparing resumes
scripts/normalize_pdf.py        Conservative PDF 1.5 normalization and integrity checks
scripts/run_resume_app.sh       One-command local web-app launcher
shared/latex/                   Shared LaTeX classes and fonts
webapp/                         Local resume workspace service and interface
AGENTS.md                       Repository rules for Codex and Antigravity
SPEC.md                         Detailed workflow contract
pyproject.toml and uv.lock      Validator dependencies
```

`master/` remains the canonical resume history; `pre-made/` contains reusable general-purpose variants across 5 tracks:
- `finance-consulting`
- `forward-deployed-engineer`
- `product-decision-data-science`
- `quantitative-research-finance`
- `software-data-engineering`

Each reusable premade contains its `resume.md` content source, domain `cover_letter.md`, compiled `_resume.tex`, and verified `Morgan_Le_Resume.pdf`. Formatting templates live under `templates/` (`Jake`, `Vmock`, `Loc`).

To render and build a Markdown resume into one of the supported LaTeX formats:

```bash
uv run python scripts/md_to_latex.py applications/<company-role>/resume.md --template jake --build
```

Supported template names are `jake` (11pt default), `vmock` (compact 10pt), and `loc`.

To compare two resume versions and see a colorized diff:

```bash
uv run python scripts/diff_resume.py pre-made/<track> applications/<company-role>
```

## Requirements

- [Codex](https://openai.com/codex/) with repository-local skill support
- [Tectonic](https://tectonic-typesetting.github.io/) on `PATH`
- [uv](https://docs.astral.sh/uv/) with Python 3.12 or later
- Optional: [Poppler](https://poppler.freedesktop.org/) for rendering PDFs during visual review

No Node.js installation or frontend build step is required. The web app uses the Python standard-library HTTP server and static HTML, CSS, and JavaScript.

On macOS, install the command-line dependencies with Homebrew:

```bash
brew install uv tectonic poppler
```

From the repository root, create or update the Python environment:

```bash
uv sync
```

## Set up your resume

1. Fork or clone this repository.
2. Update personal details and verified history in `master/resume.md`.
3. Review `AGENTS.md` and adjust content policies if needed.
4. Build any pre-made track or application resume:

   ```bash
   ./scripts/build_resume.sh pre-made/software-engineer
   ```

To compile a Markdown resume directly to PDF using any template (`jake`, `vmock`, `loc`):

```bash
python scripts/md_to_latex.py master/resume.md --template jake --build
```

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

The repository includes a local, self-hosted browser interface in `webapp/`. It opens with the verified master resume already loaded and stores each tailoring session locally. Codex still performs the analysis in the active Codex task; the web server does not start a second model session or require another API key.

### First-time setup

Run this command from the repository root:

```bash
uv sync
```

This installs the Python dependencies used for PDF inspection, normalization, and tests. Tectonic must be installed before running PDF builds.

### Start the app

Run:

```bash
./scripts/run_resume_app.sh
```

The launcher prints the address when the server is ready:

```text
Resume Tailoring Workspace: http://127.0.0.1:4173
```

Open that URL in a browser. Keep the terminal running while using the workspace and press `Ctrl+C` to stop it.

To use a different port:

```bash
./scripts/run_resume_app.sh --port 4174
```

The server accepts only loopback hosts (`127.0.0.1`, `localhost`, or `::1`) so resume data is not exposed to the local network. A quick health check is available at `http://127.0.0.1:4173/api/health`.

### Tailor a resume in the app

The visual workflow is:

1. Review the built-in master resume. The app reads `master/resume.md`; no resume upload is required.
2. Select **Tailor for a job**, then enter the company, role, optional job link, and complete job description.
3. Select **Prepare suggestions**. This creates a local session from a complete snapshot of the current master resume.
4. Send the analysis request to the active Codex task:
   - When the page is open in a Codex browser that supports workspace tools, ask Codex to analyze the saved Resume Workspace session. Codex can read the complete context and submit the recommendations directly.
   - In another browser, select **Copy request for Codex**, paste the request into the active Codex task, wait for the analysis to finish, and then select **Check for suggestions**.
5. Review one resume entry at a time in the center workspace. Select a bullet to see its recommendation and actions in the persistent right panel; use the section rail or Previous/Next controls instead of scrolling through one long document. For each bullet, approve the suggestion, keep the current wording, or select **Edit or ask AI** to edit it manually, remove it, confirm a missing fact, or request a different AI suggestion.
6. Make an explicit Include or Exclude decision for every project. Only included projects require bullet-level review; every verified work position remains represented.
7. After every recommendation has an explicit decision, build the PDF preview. If it exceeds one page, return to the specific fitting opportunities shown by the app; nothing is shortened or removed automatically.
8. Export only after every decision is resolved and the current preview passes the one-page A4 checks.

The exported files are written to `<company-role>/_resume.tex` and `<company-role>/Morgan_Le_Resume.pdf`. Export does not edit `master/resume.md`. If the target folder already exists, the app asks before overwriting that tailored version.

### Local data and resuming work

The workspace stores its disposable state under the gitignored `.resume/webapp/` directory:

```text
.resume/webapp/
  sessions/    Active tailoring-session JSON
  archive/     Archived sessions
  previews/    Temporary PDF preview sources and output
```

Open **Sessions** in the app to resume or archive an earlier session. If `master/resume.md` changes after a session starts, the app marks that session as stale and requires reconciliation before applying its suggestions.

### Troubleshooting

- **`uv: command not found`:** install uv, then run `uv sync` from the repository root.
- **`Tectonic is required`:** install Tectonic and confirm `tectonic --version` works in the same terminal.
- **Port 4173 is already in use:** start the app with another loopback port, such as `./scripts/run_resume_app.sh --port 4174`.
- **Suggestions do not appear:** make sure Codex finished the copied workspace request, then select **Check for suggestions**.
- **A session says the master changed:** use the app's restart/reconciliation action so recommendations are regenerated against the current master resume.

The master resume is read-only in the web interface. Workspace sessions, decision history, and previews are ignored by Git, while an exported tailored folder remains available for review and version control.

## Build and validate manually

Build a tailored resume or premade track from a folder:

```bash
./scripts/build_resume.sh "pre-made/software-engineer"
```

This writes only `<resume-folder>/Morgan_Le_Resume.pdf`. Validate it with:

```bash
uv run python .agents/skills/tailor-resume/scripts/validate_resume.py "pre-made/software-engineer"
```

Build a reusable premade in its default Jake format:

```bash
./scripts/build_resume.sh "pre-made/finance-consulting"
```

Build its legacy Loc format explicitly:

```bash
./scripts/build_resume.sh "pre-made/finance-consulting/Loc"
```

When creating a new premade, first preserve the approved moderncv source in `Loc/`, then generate the matching Jake source with:

```bash
uv run python scripts/convert_loc_to_jake.py \
  "pre-made/<purpose>/Loc/_resume.tex" \
  "pre-made/<purpose>/Jake/_resume.tex"
```

The generated Jake source is standalone and follows `templates/Jake/_resume.tex`; no separate Jake style file is required for Overleaf.

Run the validator tests with:

```bash
uv run python -m unittest discover -v
```

The validator checks folder contents, protected historical and contact fields, numeric claims, work-position coverage, page size and count, extractable text, hyperlinks, PDF 1.5/classic cross-reference compatibility, and ATS-hostile presentation ligatures.

## Safety and privacy

- Never invent employers, titles, dates, responsibilities, technologies, metrics, or outcomes.
- Treat only active, uncommented master-resume content as verified; never use commented-out resume items.
- Do not change a historical job title merely to match a job posting.
- Keep at least one substantive bullet for every verified work position in a tailored resume.
- Select projects explicitly for each tailored resume; project exclusion never removes them from the master source.
- Require explicit bullet-level decisions during tailoring and page fitting, plus explicit project-level inclusion decisions.
- Treat every tailored resume as a one-page A4 document.
- Review `master/resume.md` before making a fork public because it contains personal information.
- Codex does not commit or push changes unless explicitly asked.

See [`SPEC.md`](SPEC.md) for the full workflow contract.

## License

No open-source license is included. The repository may be visible and forkable on GitHub, but reuse rights remain reserved until the owner chooses a license.
