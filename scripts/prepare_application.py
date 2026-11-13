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
from output_names import output_name
from render_pdf import render_pdf_to_png
from resume_validation import validate_tailored_completeness, validate_tailored_tex


def baseline(value: str, filename: str) -> Path:
    candidate = ROOT / "pre-made" / value
    if candidate.exists():
        path = candidate.resolve()
    else:
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


def render_page_image(pdf: Path, output_prefix: Path) -> Path:
    sips_bin = shutil.which("sips")
    if sips_bin and sips_bin != "renderer":
        out_png = output_prefix.parent / f"{output_prefix.name}-1.png"
        run([sips_bin, "-s", "format", "png", "-Z", "1600", str(pdf), "--out", str(out_png)])
        return out_png
    renderer = shutil.which("pdftoppm") or shutil.which("renderer") or "pdftoppm"
    run([renderer, "-r", "120", "-png", str(pdf), str(output_prefix)])
    return output_prefix.parent / f"{output_prefix.name}-1.png"


def prepare(target: Path, bases: dict[str, Path], confirmed_facts: list[str]) -> Path:
    if not shutil.which("sips") and not shutil.which("pdftoppm"):
        raise ValueError("A PDF renderer is required for visual review (sips or pdftoppm).")
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
            pdf_name = output_name(ROOT, kind)
            pdf = staging / pdf_name
            reports[kind] = verify_submission(pdf)
            render_page_image(pdf, staging / kind)
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
    prune_reviews(reviews, keep=10)
    return review


def prune_reviews(reviews_dir: Path, keep: int = 10) -> None:
    if not reviews_dir.is_dir():
        return
    entries = [p for p in reviews_dir.iterdir() if p.is_dir()]
    entries.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    for old in entries[keep:]:
        try:
            shutil.rmtree(old)
        except OSError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", help="Explicit applications/<company-role> folder")
    parser.add_argument("--base", help="Resume baseline file or folder under pre-made/ or master/")
    parser.add_argument("--cover-letter-base", help="Cover letter baseline; supply both bases to build both")
    parser.add_argument("--confirmed-fact", action="append", default=[])
    parser.add_argument("--clean", action="store_true", help="Remove older review folders before preparing")
    args = parser.parse_args()
    try:
        if args.clean:
            reviews_dir = ROOT / ".resume/reviews"
            if reviews_dir.is_dir():
                for old in reviews_dir.iterdir():
                    if old.is_dir():
                        shutil.rmtree(old, ignore_errors=True)
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
        for kind in bases:
            image_path = review / f"{kind}-1.png"
            if image_path.is_file():
                print(f"Review image ({kind}): {image_path}")
        print("Visual review pending: inspect the page images before submitting.")
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Application preparation failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
