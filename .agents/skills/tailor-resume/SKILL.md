---
name: tailor-resume
description: Tailor, review, and build application-specific resumes in this repository through a conversational Codex workflow. Use when the user provides a job description, asks for a targeted resume, wants to review resume content section by section or job by job, points to numbered bullets for rewriting, or asks to build and verify a tailored one-page PDF.
---

# Tailor Resume

Run the resume-building session directly in the current Codex conversation. Do not recreate a chat interface or call a second model from a Python application.

## Establish the task

1. Read the repository `AGENTS.md` and inspect `git status`.
2. Read root `_resume.tex` completely. Treat it as the verified factual source.
3. Read the pasted job description completely.
4. Identify whether the user wants a new tailored version or an existing version revised.
5. State that root content will remain untouched unless the user explicitly requests an append.
6. Suggest a lowercase hyphenated folder slug. Do not overwrite an existing variant without confirmation.

Do not review the contact header. Treat section names, employer names, historical job titles, schools, and dates as locked context unless the user explicitly corrects a source fact.

## Create the review ledger

Create a gitignored session ledger under `.resume/sessions/` before beginning the review. Record:

- the job description or its path;
- the proposed target slug;
- the root `_resume.tex` hash;
- each entry and its stable source-order bullet numbers;
- each explicit decision and approved replacement text;
- newly confirmed facts;
- the current section and entry.

Update the ledger after every decision. Use it to resume an interrupted task. Remove it after the tailored source and PDF pass final verification unless the user asks to retain it.

## Review section by section

Follow source order by default: Education, Relevant Experience, Projects, then other sections. Allow the user to jump to another section.

Within each section, review one complete entry at a time. An entry is one school, employer, project, award group, or comparable unit. Present it in this shape:

```text
Relevant Experience · Entry 3/5
Boston Consulting Group (BCG) · Consultant · Jan 2025–Jun 2025

1. Current bullet...
   Recommendation: Rewrite — concise reason
   Proposed: Suggested replacement...

2. Current bullet...
   Recommendation: Keep — concise reason

3. Technologies: ...
   Recommendation: Remove — concise reason

Decisions: 0/3
```

Keep every bullet in the entry visible so the user can compare repetition and coverage. Number bullets locally within the displayed entry.

For each bullet, recommend exactly one of:

- **Keep** — retain it verbatim.
- **Rewrite** — show a complete proposed replacement using verified facts.
- **Remove** — explain what makes it lower-value or duplicative.
- **Ask** — ask one precise factual question before proposing stronger wording.

Keep reasons short and specific to the job description. Do not present scores unless the user asks for them.

## Interpret the conversation naturally

Accept natural instructions, not only slash commands. Understand requests such as:

- “Rewrite line 2 with more finance emphasis.”
- “Keep 1 and 3.”
- “Remove the technologies line.”
- “Make bullet 2 shorter.”
- “Use the recommendation for all three.”
- “Go back to BCG.”
- “Show me the whole experience section again.”

After a targeted request:

1. Apply it only to the named bullet or entry.
2. Show the revised bullet and enough surrounding entry context to compare it.
3. Ask whether to accept it when the instruction did not already clearly authorize acceptance.
4. Save the decision only after explicit acceptance.
5. Re-display the entry decision count.

Do not advance to the next entry until every bullet in the current entry has an explicit Keep, Rewrite, or Remove decision. Allow Back and Undo at any time. At a section boundary, summarize what was kept, rewritten, and removed before continuing.

## Protect factual accuracy and coverage

- Use only facts in root `_resume.tex` or facts explicitly confirmed in the current conversation.
- Never invent or strengthen metrics, responsibilities, technologies, scope, or outcomes.
- Never change a historical employer, title, school, or date merely to match a posting.
- Preserve every work position with at least one substantive bullet.
- Treat technology/tool bullets as metadata, not as the required substantive bullet.
- Preserve unrelated root content and never shorten the root for page fit.
- Add material to root only after an explicit request such as “add this to the source of truth.”
- Append root projects; do not replace existing root projects.

## Assemble the tailored version

After all entries are decided:

1. Show a compact decision summary and ask for approval to assemble the variant.
2. Copy the latest root `_resume.tex` into the approved target folder.
3. Apply only accepted tailored decisions to the copy.
4. Remove active `\newpage` commands from the tailored copy.
5. Use restrained layout compaction only when necessary. Preserve legibility and contact information.
6. Show the final source diff before the first permanent write when overwriting an existing variant.

The target folder must contain only `_resume.tex` and `Morgan_Le_Resume.pdf`.

## Build and fit interactively

Run:

```bash
./scripts/build_resume.sh "<target-slug>"
```

If the PDF exceeds one page, do not change it automatically. Show the user the relevant section or entry again and recommend specific shortening or removal options. Apply only explicit decisions, then rebuild. Repeat until the tailored PDF is exactly one A4 page.

After building, run the bundled deterministic validator:

```bash
uv run python .agents/skills/tailor-resume/scripts/validate_resume.py "<target-slug>"
```

Pass each newly confirmed numeric fact with a separate `--confirmed-fact` option.

Render the final PDF page to a temporary PNG and inspect it visually. Check clipping, overlap, broken glyphs, awkward breaks, spacing, and readability. Confirm text extraction and hyperlinks. Remove all temporary QA files.

## Finish

Report:

- the target folder and PDF;
- what was rewritten, retained, or removed;
- that root `_resume.tex` remained unchanged or exactly what was appended;
- page count, A4 status, extractable text, hyperlinks, and visual QA result;
- whether changes are uncommitted, committed, or pushed.

Do not commit or push unless explicitly requested.
