# Resume builds

Each resume version can live in its own internal folder and keep `_resume.tex` plus any local style or font files it needs.

The `source-of-truth/` folder is the comprehensive reference resume. It accumulates all verified positions, bullet points, and projects and may span multiple pages. It is not constrained to be submission-ready. Application-specific versions should start from this reference and select, reorder, or tailor the most relevant content.

Build the current version:

```bash
./scripts/build_resume.sh
```

Every build writes `Morgan_Le_Resume.pdf` inside the selected internal resume folder. The source-of-truth build is therefore stored at `source-of-truth/Morgan_Le_Resume.pdf`, while each tailored version keeps its own PDF alongside its `_resume.tex` source. Building one version never overwrites another version's PDF. Build intermediates are created in the system temporary directory and removed automatically.

To create another version:

1. Duplicate `source-of-truth/` and give the copy a new internal version name.
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
