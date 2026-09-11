---
name: tailor-cover-letter
description: Tailor, review, and build application-specific cover letters in this repository through a conversational Codex/Antigravity workflow. Use when the user provides a job description, asks for a targeted cover letter, or asks to compile and verify a one-page cover letter PDF.
---

# Tailor Cover Letter

Work directly in the current Codex or Antigravity conversation. Follow `AGENTS.md`; do not create another chat or call another model.

> **CRITICAL RULE**: Do NOT inspect, read, list, grep, or search the `applications/` directory. Files in `applications/` are ephemeral and periodically deleted by the user; browsing them is a waste of time. All tailoring references come exclusively from `pre-made/` (for track baselines) and `master/resume.md` (for verified facts, metrics, and experiences). `applications/` is strictly a write destination.

## Primary Mode: Fast 1-Turn Batch Proposal & Diff Review

When a user provides a job description (JD) and requests a targeted cover letter:

### 1. Select the Base Track & Target Path
Identify the best starting baseline from `pre-made/`:
- `pre-made/finance-consulting/cover_letter.md` (Consulting, Corporate Strategy, BizOps, Finance)
- `pre-made/forward-deployed-engineer/cover_letter.md` (Forward Deployed, Solutions Engineering, Technical PM)
- `pre-made/product-decision-data-science/cover_letter.md` (Product Data Science, Decision Science, Analytics)
- `pre-made/quantitative-research-finance/cover_letter.md` (Quant Research, Trading, Financial Engineering)
- `pre-made/software-data-engineering/cover_letter.md` (Software Engineering, Data Engineering, Backend)

*(Note: If a premade baseline does not yet exist on disk for a new track, formulate the letter using the proven 4-paragraph structure below, drawing all factual claims from `master/resume.md`.)*

Do NOT search or inspect `applications/` for prior examples or context.
Create a new application folder (e.g. `applications/<company-role>/`, lowercase hyphenated, e.g. `applications/stripe-swe/`).

### 2. Formulate the Tailored `cover_letter.md`
Generate `<target-folder>/cover_letter.md`:
- **Contact Header**: Copy the name and complete clickable contact line exactly from the private local `master/resume.md`. Never source contact details from the public template or hardcode them in the skill. Follow the header with the current date, target company, target office or team, and a concrete salutation.
- **Paragraph 1 (The Hook & Positioning)**: Role, company, current degree (Columbia MS Data Science + TA), and the overarching narrative arc linking previous operations/consulting/analytics to this specific technical or business discipline.
- **Paragraph 2 (Core Proof & Accomplishments)**: 1–2 deep, quantified achievements (e.g., BCG $10B infrastructure initiative, Shopee $100K ARR & 20% latency reduction, Ericsson automation) showing how Morgan moves between stakeholders and execution. *Never invent unverified metrics.*
- **Paragraph 3 (Technical & Builder Progression)**: Independent applications, hackathons, cloud systems, and coursework at Columbia demonstrating the hands-on engineering or modeling skills relevant to the role.
- **Paragraph 4 (Company Alignment & Call to Action)**: Specific interest in the company's product, architecture, or mission, coupled with the value proposition Morgan brings.
- **Sign-off**: `Sincerely,\nMorgan Le`.
- **Zero Placeholders**: Never leave unfilled bracket placeholders like `[Company Name]` or `______`. Every detail must be concrete.
- **1-Page A4 Budget**: Target 350–450 words to comfortably fit exactly 1 page A4 under 11pt Jake/letterhead layout.

### 3. Present the Full Unified Diff & Rationale
> **CRITICAL REQUIREMENT**: **Always show the complete, full diff**. Never truncate, summarize, or omit paragraphs. The in-chat diff must represent the complete tailored cover letter so the user can verify all details and wording changes at a glance before building.

In the same first response, show:
1. A complete in-chat Markdown diff block (`diff`) comparing the tailored `cover_letter.md` against the base premade:
   - `+` Added text / company-specific alignment
   - `-` Removed generic boilerplate
2. A brief 3-point narrative rationale:
   - **Narrative Arc**: Why this specific trajectory was emphasized for the role.
   - **Proof Points**: Which verified accomplishments and metrics were highlighted.
   - **Company Fit**: How the letter addresses the company's unique technology or business challenges.
3. Notify the user they can inspect the file directly or run:
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
