---
name: tailor-cover-letter
description: Tailor, review, and build a one-page cover letter from a supplied job description and verified applicant facts, preserving an existing approved baseline when available.
---

# Tailor Cover Letter

Use the active assistant conversation. Read `AGENTS.md` and optional `.resume/preferences.md`; require no particular model, provider, or skill loader. Do not start another model session.

## Verified sources

Read active, uncommented `master/resume.md` and the complete job description. Use an available `pre-made/<track>/cover_letter.md` baseline. Never browse `applications/` for references. Create new letters under `applications/<company-role>/cover_letter.md`; read an existing letter only when the user explicitly selects it for updates.

Derive the applicant name, contacts, education, employers, projects, achievements, and signature from their own master. The public sample is an example, not the applicant's identity. No project, university, award, or metric is universally mandatory. Apply any explicit personal preferences only when the underlying facts are verified.

## Preserve an approved baseline

Treat a selected baseline's voice, sentence order, paragraphs, and proof points as approved copy. Substitute the date, target role, company, team, and salutation. Outside those substitutions, change at most two existing body sentences and add at most one new sentence unless the user explicitly authorizes broader changes. Prefer narrow edits; explain and request approval before exceeding that scope.

When no baseline exists, an explicit request for a new cover letter authorizes drafting from verified facts. Explain that this is a new draft. Do not require a private premade folder on a fresh clone.

## Narrative and formatting

Use four connected paragraphs unless the user or baseline specifies otherwise:

1. Interest in the concrete role and company, with the applicant's actual career trajectory.
2. One or two relevant verified accomplishments and their quantified outcomes when available.
3. Relevant technical, builder, or cross-functional progression grounded in actual experience and projects.
4. Specific company alignment and a concise interview invitation.

Preserve a user-approved opening when provided; otherwise write an opening appropriate to the actual applicant. Copy the contact header from the private master and sign with the applicant's own name. Include the current date and company/team, with no applicant or company address lines. Replace every target placeholder before building.

## Build and review

Save Markdown and immediately build with:

```bash
uv run python scripts/md_to_cover_letter.py applications/<company-role>/cover_letter.md --build
```

Alternatively use `scripts/prepare_application.py` with `--cover-letter-base` to generate a full diff and review images. Default output is `Cover_Letter.pdf`; `.resume/settings.json` may override it. Verify exactly one A4 page, extractable text, and hyperlinks, then inspect the rendered page for clipping, overlap, and glyph defects. Do not present stale or failed output as verified.

Present the current PDF and complete unabbreviated Markdown diff against the baseline, including unchanged context. For a new draft, show its complete text. Explain job alignment and any baseline edits briefly. Rebuild and reverify in the same turn after requested tweaks. Respect explicit Markdown-only or deferred-build requests. Keep personalized materials private; never publish, commit, or push without authorization.
