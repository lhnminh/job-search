---
name: tailor-resume
description: Tailor, review, and build application-specific resumes in this repository through a conversational Codex workflow. Use when the user provides a job description, asks for a targeted resume, wants to review resume content section by section or job by job, points to numbered bullets for rewriting, or asks to build and verify a tailored one-page PDF.
---

# Tailor Resume

Work directly in the current Codex or Antigravity conversation. Follow `AGENTS.md`; do not create another chat or call another model.

## Primary Mode: Fast 1-Turn Batch Proposal & Diff Review

When a user provides a job description (JD) and requests a targeted resume:

### 1. Select the Base Track & Target Path
Identify the best starting base from `pre-made/`:
- `pre-made/finance-consulting` (Consulting, Corporate Strategy, BizOps, Finance)
- `pre-made/product-decision-data-science` (Product Data Science, Decision Science, Analytics)
- `pre-made/software-data-engineering` (Software Engineering, Data Engineering, Backend)
- `pre-made/analytics-business-intelligence` (BI, Reporting, Analytics Engineering)
- `pre-made/machine-learning-engineering` (ML, Deep Learning, AI Engineering)
*(Or `master/resume.md` if cross-domain).*

Create a new application folder (e.g. `applications/<company-role>/` or `<company-role>/`, lowercase hyphenated, e.g. `applications/stripe-swe/`).

### 2. Formulate the Tailored `resume.md`
Generate `<target-folder>/resume.md`:
- **Mandatory Experience**: Every verified employer and role must retain at least one substantive bullet point. Allocate more bullets/depth to roles matching the JD.
- **Projects Portfolio**: Include 1–2 high-relevance projects from `master/resume.md` that provide direct proof of skills asked for in the JD.
- **Technical Skills**: Align keywords and tools with the JD. Strictly use verified skills from `master/resume.md`—never invent technologies or proficiencies.
- **No Hallucinations**: Employer names, dates, official job titles, and verified metrics must not be altered.
- **1-Page A4 Budget**: Design line counts to comfortably fit a 1-page A4 PDF (typically ~35–45 total lines of content depending on template).

### 3. Present the Unified Diff & Rationale
In the same first response, show:
1. An in-chat Markdown diff block (`diff`) comparing the tailored `resume.md` against the base premade:
   - `+` Added bullets or projects
   - `-` Removed bullets or projects
   - `~` Adjusted skills or keywords
2. A brief 3-point rationale:
   - Why specific projects and bullet points were emphasized.
   - Which target keywords were matched.
   - Target page budget (e.g. Jake standard or Vmock compact).
3. Notify the user they can inspect the file directly, open side-by-side comparison in their IDE, or run:
   ```bash
   uv run python scripts/diff_resume.py <base-path> <target-path>
   ```

### 4. User Approval & Immediate Build (Turn 2)
- If the user approves ("Looks good", "Build it", "Approved"):
  - Compile the resume to LaTeX and PDF:
    ```bash
    uv run python scripts/md_to_latex.py <target-folder>/resume.md --template jake --build
    ```
  - If the content overflows 1 page in Jake (11pt), try `--template vmock` (compact 10pt) or propose specific line condensations.
  - Run the validator:
    ```bash
    uv run python .agents/skills/tailor-resume/scripts/validate_resume.py "<target-folder>"
    ```
  - Verify the rendered PDF is exactly one A4 page, with active hyperlinks and clean typography.
- If the user requests tweaks (e.g. *"Swap bullet 2 for bullet 3 in Shopee"*, *"Add Docker to skills"*):
  - Apply the requested edits directly to `<target-folder>/resume.md`.
  - Show the updated diff.
  - Compile and verify once approved.

---

## Detailed Entry-by-Entry Mode (Ledger)

If the user explicitly requests an entry-by-entry review or uses the interactive ledger:
- Use `.agents/skills/tailor-resume/scripts/session_ledger.py`.
- Run `uv run python .agents/skills/tailor-resume/scripts/session_ledger.py start <session-id> --target-slug <slug> --job-description-file <path>`.
- Review entries section by section and persist decisions in atomic batches before replying.

## Route Resume Workspace Sessions

When the user refers to the local Resume Workspace, its browser UI, or a session created there, use the workspace bridge:
```bash
uv run python webapp/manage.py sessions
uv run python webapp/manage.py context <session-id>
uv run python webapp/manage.py submit <session-id> <analysis-json-file>
uv run python webapp/manage.py revise <session-id> <request-id> <suggestion-json-file>
```

## Route Reusable Premade Work

When the user asks to create or update a reusable variant under `pre-made/`:
- Maintain `resume.md`, compiled `_resume.tex`, and verified `Morgan_Le_Resume.pdf`.
- Compile using `uv run python scripts/md_to_latex.py <premade-folder>/resume.md --template jake --build`.
