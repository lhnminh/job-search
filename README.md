# Agentic Resume Customization

A local-first system for turning one comprehensive resume into focused, job-specific applications with Codex.

Bring your own resume, add any reusable content or layout templates you prefer, and give the agent a job description. The workflow selects relevant experience, proposes targeted wording, shows the complete diff for review, and builds a verified one-page A4 PDF without inventing facts.

[View the example resume](public/resume.md) · [Download the example PDF](public/Morgan_Le_Resume.pdf)

## What it does

- Uses your private master resume as the source of truth.
- Reuses optional track-specific baselines for engineering, data science, finance, consulting, or other roles.
- Reviews every proposed change with you in the active Codex conversation.
- Preserves verified employers, titles, dates, metrics, and responsibilities.
- Builds ATS-readable PDFs with working hyperlinks.
- Keeps private resumes, applications, and cover letters out of Git.

## Quick start

### 1. Clone and install

```bash
git clone [<repository-url>](https://github.com/lhnminh/job-search)
cd job-search

# macOS
brew install uv tectonic poppler
uv sync
```

Requirements:

- [Codex](https://openai.com/codex/) with repository-local skill support
- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- [Tectonic](https://tectonic-typesetting.github.io/) for PDF builds
- [Poppler](https://poppler.freedesktop.org/) for visual PDF checks

### 2. Add your resume

Create the private workspace and add your comprehensive resume:

```bash
mkdir -p master pre-made applications
cp public/resume.md master/resume.md
```

Replace the example content in `master/resume.md` with your own verified experience. This file is your private source of truth and is ignored by Git.

The expected Markdown structure is simple:

```markdown
# Your Name

[email@example.com](mailto:email@example.com) | 212-555-0100 | [Portfolio](https://example.com)

## Experience

### Company | Role | Location
*Jan 2024 – Present*
- Accomplished a specific outcome using a specific skill.
- **Technologies:** Python, SQL
```

### 3. Add your own templates (optional)

The included Jake layout works out of the box. You can also add private, reusable content baselines:

```text
pre-made/
  software-engineering/
    resume.md
    cover_letter.md       # optional
  data-science/
    resume.md
```

Formatting templates live in `templates/`. Add or adapt a layout there if you want a different visual style.

### 4. Tailor for a job

Open the repository in Codex and ask:

```text
Use $tailor-resume to tailor my resume for this job description:

<paste the complete job description>
```

The agent will:

1. Read the job description and your private resume.
2. Select the closest optional baseline, when available.
3. Propose targeted bullets and project choices using verified facts only.
4. Show the complete Markdown diff for approval.
5. Save the approved version under `applications/<company-role>/`.
6. Build and validate an ATS-readable, one-page A4 PDF.

For a cover letter, use the same flow with `$tailor-cover-letter`.

## Output

Each private application is self-contained:

```text
applications/<company-role>/
  resume.md
  _resume.tex
  Morgan_Le_Resume.pdf
  cover_letter.md                 # optional
  _cover_letter.tex               # optional
  Morgan_Le_Cover_Letter.pdf      # optional
```

`applications/` is ignored by Git, so generated application materials remain local.

## Useful commands

Build a Markdown resume with the default Jake template:

```bash
uv run python scripts/md_to_latex.py \
  applications/<company-role>/resume.md \
  --template jake \
  --build
```

Compare a baseline with a tailored resume:

```bash
uv run python scripts/diff_resume.py \
  pre-made/<track> \
  applications/<company-role>
```

Validate a completed resume:

```bash
uv run python .agents/skills/tailor-resume/scripts/validate_resume.py \
  applications/<company-role>
```

Run the test suite:

```bash
uv run python -m unittest discover -v
```

## Optional visual workspace

Start the local Resume Workspace if you prefer reviewing suggestions in a browser:

```bash
./scripts/run_resume_app.sh
```

Open `http://127.0.0.1:4173`. The server binds to loopback only, stores session data under `.resume/`, and uses the active Codex conversation rather than starting a separate model session.

## Public and private files

Only the approved example resume and reusable system code belong in the public repository.

| Path | Purpose | Tracked |
| --- | --- | --- |
| `public/` | Approved public resume and PDF | Yes |
| `templates/` | Generic formatting templates | Yes |
| `.agents/skills/`, `scripts/`, `webapp/` | Agentic workflow and tooling | Yes |
| `master/` | Comprehensive personal resume | No |
| `pre-made/` | Personal reusable baselines | No |
| `applications/` | Tailored resumes and cover letters | No |
| `.resume/` | Sessions, previews, and private backups | No |

Previously committed private files remain in Git history until the history is rewritten. Ignoring them prevents future commits but does not erase earlier revisions.

## Core guarantees

- Never invent experience, metrics, technologies, dates, or outcomes.
- Never change an official historical job title to match a posting.
- Keep every verified work position represented in tailored resumes.
- Treat projects as selectable; removing one from an application never removes it from the master resume.
- Require explicit review before accepting rewritten content.
- Produce exactly one A4 page for every tailored resume.
- Never commit or push without explicit permission.

See [AGENTS.md](AGENTS.md) for repository rules and [SPEC.md](SPEC.md) for the detailed workflow contract.

## License

No open-source license is included. The repository may be visible and forkable on GitHub, but reuse rights remain reserved until the owner chooses a license.
