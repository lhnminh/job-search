#!/usr/bin/env python3
"""Build, validate, and prepare a complete private application review in one action."""

from __future__ import annotations

import argparse
import difflib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

from verify_submission_pdf import ROOT, verify_submission
from resume_validation import validate_tailored_completeness, validate_tailored_tex


def baseline(value: str, filename: str) -> Path:
    path = Path(value).resolve()
    if not any(path.is_relative_to(ROOT / directory) for directory in ("pre-made", "master")):
        raise ValueError("Baselines must come from pre-made/ or master/.")
    if path.is_dir():
        path = (path / filename).resolve()
    if not any(path.is_relative_to(ROOT / directory) for directory in ("pre-made", "master")):
        raise ValueError("Baseline symlinks must stay within pre-made/ or master/.")
    if not path.is_file():
        raise ValueError(f"Baseline not found: {path}")
    return path


def target_folder(value: str) -> Path:
    path = Path(value).resolve()
    applications = (ROOT / "applications").resolve()
    if path.parent != applications or path == applications:
        raise ValueError("Select one application folder directly under applications/.")
    # Resolving symlinks must not allow an output to escape the private boundary.
    if not path.is_relative_to(ROOT / "applications"):
        raise ValueError("Application folder must stay inside applications/.")
    return path


def full_diff(base: Path, target: Path) -> str:
    before = base.read_text(encoding="utf-8").splitlines()
    after = target.read_text(encoding="utf-8").splitlines()
    return "\n".join(difflib.unified_diff(
        before, after, fromfile=str(base), tofile=str(target),
        n=max(len(before), len(after)), lineterm="",
    )) or "No changes."


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def prepare(target: Path, bases: dict[str, Path], confirmed_facts: list[str]) -> Path:
    renderer = shutil.which("pdftoppm")
    if not renderer:
        raise ValueError("Poppler is required for visual review. Install it with: brew install poppler")
    # Read only explicitly selected inputs; never enumerate applications/.
    for kind in bases:
        if not (target / f"{kind}.md").is_file():
            raise ValueError(f"Missing input: {target / f'{kind}.md'}")
    master = (ROOT / "master/resume.md").read_text(encoding="utf-8") if "resume" in bases else ""
    reviews = ROOT / ".resume/reviews"
    reviews.mkdir(parents=True, exist_ok=True)
    review = reviews / uuid.uuid4().hex
    with tempfile.TemporaryDirectory(prefix="prepare-", dir=reviews) as temporary:
        staging = Path(temporary)
        reports = {}
        output_names = []
        for kind, base in bases.items():
            markdown = target / f"{kind}.md"
            shutil.copyfile(markdown, staging / markdown.name)
            (staging / f"{kind}.diff").write_text(full_diff(base, markdown) + "\n", encoding="utf-8")
            converter = "md_to_latex.py" if kind == "resume" else "md_to_cover_letter.py"
            command = [sys.executable, str(ROOT / "scripts" / converter), str(staging / markdown.name)]
            if kind == "resume":
                command += ["--template", "jake", "--output", str(staging / "_resume.tex")]
                run(command)
                source = (staging / "_resume.tex").read_text(encoding="utf-8")
                errors = validate_tailored_tex(master, source, confirmed_facts)
                errors += validate_tailored_completeness(master, source)
                if errors:
                    raise ValueError("Resume validation failed: " + " ".join(errors))
                run([str(ROOT / "scripts/build_resume.sh"), str(staging.relative_to(ROOT))])
            else:
                run(command + ["--build"])
            pdf_name = "Morgan_Le_Resume.pdf" if kind == "resume" else "Morgan_Le_Cover_Letter.pdf"
            pdf = staging / pdf_name
            reports[kind] = verify_submission(pdf)
            run([renderer, "-r", "120", "-png", str(pdf), str(staging / kind)])
            output_names += [f"_{kind}.tex", pdf_name]
        (staging / "report.json").write_text(json.dumps({
            "target": str(target), "pdf_checks": reports,
            "resume_content_checked": "resume" in bases,
            "cover_letter_facts_checked": False,
            "visual_review": "pending: inspect the generated page images",
        }, indent=2) + "\n", encoding="utf-8")
        # Both documents must pass before any existing submission output changes.
        shutil.copytree(staging, review)
        for name in output_names:
            shutil.copyfile(staging / name, target / name)
    return review


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", help="Explicit applications/<company-role> folder")
    parser.add_argument("--base", help="Resume baseline file or folder under pre-made/ or master/")
    parser.add_argument("--cover-letter-base", help="Cover letter baseline; supply both bases to build both")
    parser.add_argument("--confirmed-fact", action="append", default=[])
    args = parser.parse_args()
    try:
        target = target_folder(args.target)
        bases = {}
        if args.base:
            bases["resume"] = baseline(args.base, "resume.md")
        if args.cover_letter_base:
            bases["cover_letter"] = baseline(args.cover_letter_base, "cover_letter.md")
        if not bases:
            raise ValueError("Supply --base, --cover-letter-base, or both.")
        review = prepare(target, bases, args.confirmed_fact)
        for kind in bases:
            print((review / f"{kind}.diff").read_text(encoding="utf-8"))
        print(f"PDF checks passed. Review files: {review}")
        print("Visual review pending: inspect the page images before submitting.")
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Application preparation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
