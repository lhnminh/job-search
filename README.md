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

## Interactive Codex CLI

The repository includes a local Codex-powered terminal tool for creating and reviewing resume variants. It uses the Codex authentication already configured on the machine; personal interactive use does not require a separate API key.

Start the mode-selection menu:

```bash
uv run resume
```

The CLI checks the existing local Codex login before starting. Confirm it manually with:

```bash
codex login status
```

When pasting a job description, finish the paste with a line containing only `.done`.

Create a one-page tailored resume from a pasted job description:

```bash
uv run resume tailor
```

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

The root source is append-only when changed through the CLI. Tailored versions can be rewritten, but accepted content reaches the root only through an explicit `/source` action. Every tailored version created by the CLI must compile to exactly one A4 page. See `SPEC.md` for the complete behavior contract.

During guided review, ordinary text is sent to Codex as a revision instruction. The available shortcuts are `/accept`, `/keep`, `/regenerate`, `/source`, `/skip`, `/back`, `/undo`, and `/done`. The tool also pauses after each section for a section-level review.

Every successful build is checked for A4 size, page count, extractable text, and hyperlinks. The PDF is then rendered page by page for Codex visual inspection. Temporary page images are deleted automatically.

Run the test suite:

```bash
uv run python -m unittest discover -v
```
