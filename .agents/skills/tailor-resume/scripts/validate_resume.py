#!/usr/bin/env python3
"""Validate one built tailored resume against the repository source of truth."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").is_file() and (parent / "_resume.tex").is_file():
            return parent
    raise RuntimeError("Could not locate the resume repository root")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", help="Tailored resume folder slug")
    parser.add_argument(
        "--confirmed-fact",
        action="append",
        default=[],
        help="A user-confirmed fact allowed in addition to root _resume.tex; repeat as needed",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    root = repository_root()
    sys.path.insert(0, str(root / "src"))

    from resume_cli.build import verify_pdf
    from resume_cli.resume import (
        resume_path,
        validate_tailored_completeness,
        validate_tailored_tex,
    )

    source_path = resume_path(root, arguments.target)
    target_directory = source_path.parent
    pdf_path = target_directory / "Morgan_Le_Resume.pdf"
    errors: list[str] = []

    if not source_path.is_file():
        errors.append(f"Tailored source not found: {source_path}")
    if not pdf_path.is_file():
        errors.append(f"Tailored PDF not found: {pdf_path}")
    allowed_files = {"_resume.tex", "Morgan_Le_Resume.pdf"}
    if target_directory.is_dir():
        extras = sorted(path.name for path in target_directory.iterdir() if path.name not in allowed_files)
        if extras:
            errors.append("Unexpected files in tailored folder: " + ", ".join(extras))

    report = None
    if not errors:
        root_source = (root / "_resume.tex").read_text(encoding="utf-8")
        tailored_source = source_path.read_text(encoding="utf-8")
        errors.extend(
            validate_tailored_tex(root_source, tailored_source, arguments.confirmed_fact)
        )
        errors.extend(validate_tailored_completeness(root_source, tailored_source))
        try:
            report = verify_pdf(pdf_path)
        except Exception as exc:
            errors.append(str(exc))
        if report is not None and report.pages != 1:
            errors.append(f"Tailored PDF must be exactly one page; got {report.pages}")

    result = {
        "approved": not errors,
        "target": arguments.target,
        "source": str(source_path.relative_to(root)),
        "pdf": str(pdf_path.relative_to(root)),
        "errors": errors,
    }
    if report is not None:
        result["pdf_report"] = {
            "pages": report.pages,
            "a4": report.a4,
            "links": report.links,
            "extracted_characters": report.extracted_characters,
        }
    print(json.dumps(result, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
