# Resume builds

The comprehensive source-of-truth resume lives at the repository root as two files:

- `_resume.tex` - editable content for that version.
- `Morgan_Le_Resume.pdf` - rendered output for that version.

Each tailored resume version lives in its own internal folder with the same two-file structure. Shared LaTeX classes, styles, and fonts live once under `shared/latex/`. The build script combines the selected `_resume.tex` with those shared files in a temporary compilation directory.

```text
_resume.tex                     # Comprehensive source of truth
Morgan_Le_Resume.pdf            # Rendered source of truth
shared/latex/                  # Shared moderncv files and fonts
finance-consulting/
  _resume.tex
  Morgan_Le_Resume.pdf
macquarie-asset-management/
  _resume.tex
  Morgan_Le_Resume.pdf
```

The root `_resume.tex` is the comprehensive reference resume. It accumulates all verified positions, bullet points, and projects and may span multiple pages. It is not constrained to be submission-ready. Application-specific versions should start from this reference and select, reorder, or tailor the most relevant content.

Build the current version:

```bash
./scripts/build_resume.sh
```

With no argument, the build writes the source-of-truth PDF to the repository root. A tailored build writes `Morgan_Le_Resume.pdf` inside the selected internal resume folder. Building one version never overwrites another version's PDF. Build intermediates are created in the system temporary directory and removed automatically.

To create another version:

1. Create a new internal folder.
2. Copy only the root `_resume.tex` into it.
3. Select, reorder, and tailor the relevant content in the copied `_resume.tex`.
4. Run the script with the new internal folder name to create its PDF.

For example:

```bash
./scripts/build_resume.sh "finance-consulting"
```

The `finance-consulting/` version emphasizes consulting, commercial finance, pricing, market analysis, P&L analysis, and real estate analytics.

Build the Macquarie Asset Management application version:

```bash
./scripts/build_resume.sh "macquarie-asset-management"
```

The `macquarie-asset-management/` version emphasizes real estate, client solutions, commercial analytics, quantitative analysis, Excel, infrastructure, and long-term value creation.

Rebuilding a version intentionally replaces only the `Morgan_Le_Resume.pdf` inside that same internal folder. The script uses the installed `tectonic` command, or the executable specified by `RESUME_TECTONIC_BIN`.

## Python environment

The project uses uv with Python 3.12. Create or update the local environment from the committed lockfile:

```bash
uv sync
```

Run future Python tooling through uv:

```bash
uv run python --version
```

Add a project dependency with `uv add <package>`. Commit both `pyproject.toml` and `uv.lock` whenever dependencies change.

## Conversational Codex skill

The primary tailoring workflow is the repo-specific `tailor-resume` skill. It runs directly in your current Codex conversation, so there is no nested chat interface and no separate API key.

Start a new Codex task in this repository and say:

```text
Use $tailor-resume to tailor my resume for this job description:

<paste job description>
```

The skill reviews Education, Relevant Experience, Projects, and other sections in order. Within each section it shows one complete school, job, or project with all bullets numbered. You can respond naturally:

```text
Rewrite line 2 with more finance emphasis.
Keep 1 and 3.
Remove the technologies line.
Show me the whole experience section again.
```

Every bullet requires an explicit decision. Codex records decisions in a temporary gitignored session ledger, creates or updates the tailored folder only after review, and never changes the source of truth unless you explicitly request an append. Page fitting is also conversational: nothing is removed or shortened automatically.

After building, the skill runs a deterministic source/PDF validator and performs visual QA. Tailored folders still contain only `_resume.tex` and `Morgan_Le_Resume.pdf`.

## Legacy interactive CLI

The Python terminal application remains available as a fallback while the skill-first workflow is validated. It uses the Codex authentication already configured on the machine.

Start the mode-selection menu:

```bash
uv run resume
```

The CLI checks the existing local Codex login before starting. Confirm it manually with:

```bash
codex login status
```

When pasting a job description, finish the paste with a line containing only `.done`.

Create a one-page tailored resume through an interactive entry-by-entry session:

```bash
uv run resume tailor
```

Tailor mode starts with the complete root resume. Codex analyzes all content lines in one batch for speed, then the CLI presents one complete education item, job, or project at a time. All bullets are numbered and remain visible together, while contact details are skipped and employer/title/date headers are locked.

You can target a particular bullet while retaining the complete entry as context—for example, `/rework 2 emphasize the financial model`. Use `/accept 2`, `/keep 2`, or `/remove 2` to decide individual bullets; `/accept-all` and `/keep-all` handle the undecided bullets in the visible entry. `/next` is available only after every bullet in that entry has a saved decision. `/back`, `/undo`, and `/quit` handle navigation and resumability.

After every entry has been reviewed, the CLI builds a temporary preview. If it is longer than one page, the CLI asks you to shorten, remove, or keep individual lines until it fits. It does not automatically cut positions or bullets. Sessions are saved after each decision and can be continued with `uv run resume resume`. The non-interactive `--yes` option is disabled because it would bypass the entry review.

Review a resume bullet by bullet and section by section:

```bash
uv run resume review
uv run resume review "finance-consulting"
```

Resume the latest unfinished conversation:

```bash
uv run resume resume
```

Check authentication, source parsing, available versions, and unfinished sessions:

```bash
uv run resume status
```

The root source is append-only when changed through the CLI. Tailored versions can be rewritten, but accepted content reaches the root only through an explicit `/source` action. Every generated variant must fit exactly one A4 page, preserve every work position with at least one substantive bullet, and allocate extra space to the roles most relevant to the job. See `SPEC.md` for the complete behavior contract.

During the separate `review` mode, ordinary text is sent to Codex as a revision instruction. Its available shortcuts are `/accept`, `/keep`, `/regenerate`, `/source`, `/skip`, `/back`, `/undo`, and `/done`. The tool also pauses after each section for a section-level review.

Every successful build is checked for A4 size, page count, extractable text, and hyperlinks. The PDF is then rendered page by page for Codex visual inspection. Temporary page images are deleted automatically.

The CLI uses Poppler's `pdftoppm` when it is available and otherwise falls back to the project-managed PyMuPDF dependency. Run `uv sync` after pulling dependency changes. PDF-renderer failures stop immediately and are never sent back to Codex as resume-rewriting instructions.

Run the test suite:

```bash
uv run python -m unittest discover -v
```
