# Portable chat workflow

Tailoring and review happen entirely in your active assistant conversation. The repository's tools do not call a model, store model credentials, or require a particular provider. There is no web application, server, browser interface, or JSON suggestion bridge.

## With repository access

Clone and initialize using README.md. Ask your assistant to read `AGENTS.md`, optional `.resume/preferences.md`, and the applicable `.agents/skills/tailor-resume/SKILL.md` or `.agents/skills/tailor-cover-letter/SKILL.md`. Automatic skill discovery is optional: explicit file paths are the portable entry point.

For a resume, paste the complete job description and ask:

```text
Read AGENTS.md and .agents/skills/tailor-resume/SKILL.md.
Use my active master/resume.md facts to tailor a new resume for this job.
Build and validate it, show the full diff and PDF, and explain changes step by step.

<complete job description>
```

For a letter, load `.agents/skills/tailor-cover-letter/SKILL.md` instead. The assistant selects an available private baseline or uses your master. New clones do not need premade files. Applicants must replace demo facts with their own verified content before applying.

The assistant writes Markdown under `applications/<company-role>/`, builds with Jake, checks the one-page A4 PDF, inspects page images, and presents the entire diff in chat. Use this deterministic command for a resume:

```bash
uv run python scripts/prepare_application.py applications/<company-role> --base master/resume.md
```

Use an actual `pre-made/<track>` baseline when available. `--cover-letter-base` prepares an optional letter in the same action. A new letter without a baseline can be built with `scripts/md_to_cover_letter.py <selected-letter> --build`. Default filenames are `Resume.pdf` and `Cover_Letter.pdf`; `.resume/settings.json` can override them.

An assistant unable to inspect images must report visual review as pending. The user can review the generated page images. Automated PDF checks cannot establish that the layout has no clipping or overlap.

## Without repository access

Attach or paste `AGENTS.md`, the applicable skill file, your active verified master content, any selected baseline, and the complete job description into your preferred chat. Request a complete tailored Markdown document and full diff, with no invented facts.

Save the returned Markdown as `applications/<company-role>/resume.md` or `cover_letter.md` locally. Run the same preparation/build commands, inspect the images, and return any build errors or requested wording changes to the same chat. There is no schema or separate application to operate. Do not share unrelated private files with the assistant.

## Optional detailed review

If you want entry-by-entry review, the existing `session_ledger.py` tool persists decisions under gitignored `.resume/sessions/`. The assistant presents numbered bullets in chat and records your explicit choices; it never accepts suggestions on your behalf. The fast full-diff workflow remains the default.

## Compatibility

The portable interface is Markdown files and local Python/Bash commands. Codex metadata in `agents/openai.yaml` remains an optional shortcut. No live compatibility test with every assistant product is claimed. macOS builds are tested locally; Linux/WSL setup is documented. Native Windows shell builds require a Linux environment such as WSL.
