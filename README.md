# Resume builds

Each resume version can live in its own internal folder and keep `_resume.tex` plus any local style or font files it needs.

The `resume-general/` folder is the comprehensive reference resume. It accumulates all verified positions, bullet points, and projects and may span multiple pages. It is not constrained to be submission-ready. Application-specific versions should start from this reference and select, reorder, or tailor the most relevant content.

Build the current version:

```bash
./scripts/build_resume.sh
```

Every build writes the selected internal version to `output/pdf/Morgan_Le_Resume.pdf`. The public filename is fixed even when a different internal resume version is selected. Build intermediates are created in the system temporary directory and removed automatically.

To create another version:

1. Duplicate `resume-general/` and give the copy a new internal version name.
2. Select, reorder, and tailor the relevant content in that version's `_resume.tex`.
3. Run the script with the new internal folder name.

For example:

```bash
./scripts/build_resume.sh "resume-finance-consulting"
```

The `resume-finance-consulting/` version emphasizes consulting, commercial finance, pricing, market analysis, P&L analysis, and real estate analytics.

Build the Macquarie Asset Management application version:

```bash
./scripts/build_resume.sh "resume-macquarie-asset-management"
```

The `resume-macquarie-asset-management/` version emphasizes real estate, client solutions, commercial analytics, quantitative analysis, Excel, infrastructure, and long-term value creation.

Running a build for another internal version intentionally replaces the existing `Morgan_Le_Resume.pdf`. The script uses the installed `tectonic` command, or the executable specified by `RESUME_TECTONIC_BIN`.

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
