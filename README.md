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
