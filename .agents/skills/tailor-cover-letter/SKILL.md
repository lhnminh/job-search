---
name: tailor-cover-letter
description: Tailor, review, and build application-specific cover letters in this repository while preserving the selected baseline and making only job-relevant additions or minimal edits. Use when the user provides a job description, asks for a targeted cover letter, or asks to compile and verify a one-page cover letter PDF.
---

# Tailor Cover Letter

Work directly in the current Codex or Antigravity conversation. Follow `AGENTS.md`; do not create another chat or call another model.

> **CRITICAL RULE**: Do NOT inspect, read, list, grep, or search the `applications/` directory. Files in `applications/` are ephemeral and periodically deleted by the user; browsing them is a waste of time. All tailoring references come exclusively from `pre-made/` (for track baselines) and `master/resume.md` (for verified facts, metrics, and experiences). `applications/` is strictly a write destination.

> **PROOFREAD BASELINE CONTRACT**: Treat every selected `pre-made/*/cover_letter.md` as user-approved copy. Its wording, voice, sentence order, paragraph order, and proof points are locked by default. Tailoring is a small patch to that letter, not an opportunity to rewrite, improve, modernize, or restyle it.

## Hard Preservation Limits

Without the user's explicit approval for a broader rewrite:

- Always make the required literal substitutions for date, company, role, team (if applicable), and salutation. These substitutions do not count toward the body-edit limit.
- Outside those substitutions, materially edit no more than **two existing body sentences total** and add no more than **one new body sentence total**.
- Prefer a word or short-phrase substitution inside an existing sentence over replacing the whole sentence. Prefer leaving a secondary job requirement uncovered over forcing an unnatural or weakly supported rewrite.
- Do not change a sentence whose only proposed benefit is stronger style, smoother flow, more enthusiasm, more keywords, or a more polished tone.
- Do not replace an existing accomplishment merely because another accomplishment is also relevant. Replace one only when the current proof point is materially mismatched and the verified replacement covers a central job requirement.
- If adequate tailoring would exceed this limit, stop before making the broader edits. Show which additional sentences would need to change, explain why, and ask the user to approve that expanded scope.

Apply an explicit user-requested wording change exactly and narrowly. Do not use that request as permission to revise nearby sentences or the rest of the paragraph.

## Primary Mode: Preservation-First Proposal & Diff Review

When a user provides a job description (JD) and requests a targeted cover letter:

### 1. Select the Base Track & Target Path
Identify the best starting baseline from `pre-made/`:
- `pre-made/finance-consulting/cover_letter.md` (Consulting, Corporate Strategy, BizOps, Finance)
- `pre-made/forward-deployed-engineer/cover_letter.md` (Forward Deployed, Solutions Engineering, Technical PM)
- `pre-made/product-decision-data-science/cover_letter.md` (Product Data Science, Decision Science, Analytics)
- `pre-made/quantitative-research-finance/cover_letter.md` (Quant Research, Trading, Financial Engineering)
- `pre-made/software-data-engineering/cover_letter.md` (Software Engineering, Data Engineering, Backend)

Do NOT search or inspect `applications/` for prior examples or context.
Create a new application folder (e.g. `applications/<company-role>/`, lowercase hyphenated, e.g. `applications/stripe-swe/`).

When a premade baseline exists, copy it as the starting text. Do not redraft the letter from scratch.

### 2. Adapt the Baseline with Minimal Changes
Create `<target-folder>/cover_letter.md` using this order of operations:

1. Copy the selected baseline verbatim.
2. Fill only the literal target fields: date, company, role, team (if applicable), and salutation (do not add address or location).
3. Extract the job's few central responsibilities and qualifications; do not attempt to mirror every keyword in the JD.
4. Mark requirements already supported by the unchanged baseline. Do not edit those sentences.
5. For any central uncovered requirement, map it to verified evidence in `master/resume.md` and make the smallest possible phrase-level change within the hard preservation limits.
6. Replace or remove existing wording only when it is inaccurate for the target, materially conflicts with the job, or must be trimmed to keep the letter to one page.

Do not rewrite for stylistic variety, swap synonyms merely to sound tailored, reorganize the narrative, or polish unrelated passages. Keep the baseline's tone, paragraph order, accomplishments, and wording wherever possible. Every substantive addition must address a specific job requirement and must be supported by `master/resume.md`; never invent a metric, responsibility, technology, or outcome.

Treat the premade letter's human voice as part of the template. Preserve its sentence rhythm, level of formality, and plainspoken wording. Do not introduce inflated corporate language, generic enthusiasm, ornamental transitions, excessive adjectives, or polished-sounding phrases that are not necessary for the target role. Every changed body sentence must have a concrete reason: target details, a missing job requirement, factual accuracy, or the one-page limit. If the reason is only that the rewrite sounds smoother, more impressive, or more tailored, keep the original sentence.

Retain the baseline's four-paragraph structure and word budget:

- **Word Count Budget (270–320 words)**: The 4 body paragraphs must consistently total between 270 and 320 words. This budget guarantees a single-page A4 layout under Jake typography alongside header, date, recipient, and closing blocks without overflow or awkward page-splitting.
- **Paragraph 1 (The Hook & Positioning)**: State target role and company. Position as Columbia MS Data Science student with three years of professional experience across consulting, operations, and analytics. Replace only role, company, and team placeholders.
- **Paragraph 2 (Operational & Technical Proof)**:
  - *Software Engineering / Full-Stack*: Highlight Shopee pipeline consolidation (20% manual time reduction, Python/SQL) + independent builder projects and hackathons (always touching on the MongoDB Atlas / Vector Search self-repairing computer use project, 9× speedup, 3rd place).
  - *Consulting / Strategy / Analytics*: Highlight Shopee $100K revenue / 25% YoY growth + multi-source pipeline consolidation (20% reduction) or Peloton $800K procurement savings + MongoDB Hackathon live demo / impact.
  - *AI / Agent Engineering*: Highlight Shopee data pipeline automation + agentic / full-stack architectures, always highlighting the MongoDB Harness Engineering Hackathon self-repairing computer-use harness (MongoDB Atlas, Vector Search, 9× speedup, 3rd place).
  - *Data Science / Decision Science*: Highlight Shopee seller/sales performance statistical analysis ($100K revenue, 25% YoY) + automated reporting workflows + MongoDB Vector Search retrieval project.
- **Paragraph 3 (Cross-Functional Bridge & Strategic Impact)**:
  - *SWE / Tech*: Bridge cross-functional experience from BCG, Peloton, and Shopee (translating requirements, navigating operational constraints, moving analysis into execution).
  - *Consulting / BizOps / Analytics*: Highlight BCG $10B infrastructure initiative, pricing/financial modeling, and executive decision-making.
- **Paragraph 4 (Company Alignment & Call to Action)**: Connect directly to the company's engineering challenge, product mission, or team focus (e.g. Scale's reliable AI, Nominal's hardware data infra, ZS Insights & Analytics) + professional interview CTA.

- **Always Touch on MongoDB Project**: Every cover letter must touch on the verified MongoDB project from `master/resume.md` ([Self-Improving Computer Use](https://github.com/lhnminh/recursive-computer-use) | MongoDB's Harness Engineering Hackathon 3rd Place, self-repairing agent harness using Python, MongoDB Atlas, and Vector Search to achieve a 9× speedup, presented to 1,000+ MongoDB.local participants). Never remove or omit this project when tailoring.
- **Contact Header**: Copy the name and complete clickable contact line exactly from the private local `master/resume.md`:
  `[ml5536@columbia.edu](mailto:ml5536@columbia.edu) | 347-774-6979 | [lhnminh.github.io](https://lhnminh.github.io/) | [linkedin.com/in/morganhle](https://www.linkedin.com/in/morganhle/)`.
  Never source contact details from the public template or hardcode them in the skill. Follow the header with the current date, target company (or team), and a concrete salutation.
- **No Location / Address**: Do not include applicant location or company address/location anywhere in the cover letter (no street address, city, state, or office location). The recipient block consists solely of the target company name (and optional team if applicable).
- **Sign-off**: `Sincerely,\nMorgan Le`.
- **Zero Placeholders**: Never leave unfilled bracket placeholders like `[Company Name]` or `______`. Every detail must be concrete.
- **1-Page A4 Budget**: Keep the letter at exactly one A4 page. If additions cause overflow, first remove the least relevant generic phrase or sentence; do not broadly rewrite or compress the whole letter.
- **Output File Hygiene**: Built PDF must be `<target-folder>/Morgan_Le_Cover_Letter.pdf`. Never create malformed or auxiliary PDF files. Validate build using `./scripts/build_cover_letter.sh <target-folder>`.

If no suitable premade baseline exists, tell the user that no proofread baseline matches and ask whether they want to use the closest existing track with minimal edits or authorize a new draft. Do not silently compose a new letter.

Before presenting or building, compare the target against the baseline sentence by sentence. Revert every body change that is not required for target-field accuracy, a central uncovered requirement, factual accuracy, or the one-page limit. Confirm that the hard preservation limits were met; if they were not, obtain explicit approval for the broader rewrite.

### 3. Present the Full Unified Diff & Rationale
> **CRITICAL REQUIREMENT**: **Always show the complete, full diff**. Never truncate, summarize, or omit paragraphs. The in-chat diff must represent the complete tailored cover letter so the user can verify all details and wording changes at a glance before building.

In the same first response, show:
1. A complete in-chat Markdown diff block (`diff`) comparing the tailored `cover_letter.md` against the base premade:
   - `+` Job-requirement coverage and company-specific alignment
   - `-` Only wording that had to be replaced or trimmed
2. A brief 3-point narrative rationale:
   - **Requirements Added**: Which job requirements were missing from the baseline and what verified evidence was added for each.
   - **Preserved Content**: Which core paragraphs and proof points remained unchanged.
   - **Company Fit**: What minimal company-specific language was added and why.
3. A short **Change Budget** line stating how many existing body sentences were materially edited and how many new body sentences were added, excluding literal target-field substitutions.
4. Notify the user they can inspect the file directly or run:
   ```bash
   uv run python scripts/diff_cover_letter.py <base-path> <target-path>
   ```

### 4. User Approval & Immediate Build (Turn 2)
- If the user approves ("Looks good", "Build it", "Approved"):
  - Compile to LaTeX and build the normalized PDF:
    ```bash
    uv run python scripts/md_to_cover_letter.py <target-folder>/cover_letter.md --build
    ```
  - Verify that:
    1. The build produces `Morgan_Le_Cover_Letter.pdf`.
    2. The output is **strictly 1 page A4** (the build script will warn if > 1 page).
    3. No unfilled brackets (`[...]`) or blanks exist.
    4. Hyperlinks and typography render cleanly.
- If the user requests tweaks:
  - Apply edits to `<target-folder>/cover_letter.md`.
  - **Always show the complete updated full diff** against the base.
  - Compile and verify once approved.
