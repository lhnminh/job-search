"""Resolve private output-name preferences without assuming an applicant identity."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def output_name(repository: Path, kind: str) -> str:
    default = "Resume.pdf" if kind == "resume" else "Cover_Letter.pdf"
    settings = repository / ".resume/settings.json"
    values = json.loads(settings.read_text()) if settings.is_file() else {}
    if not isinstance(values, dict):
        raise ValueError(".resume/settings.json must contain a JSON object.")
    name = values.get(f"{kind}_pdf", default)
    if not isinstance(name, str) or not name.endswith(".pdf") or any(c in name for c in '/\\\r\n') or name.startswith("."):
        raise ValueError("PDF filenames must be plain filenames ending in .pdf.")
    other = "cover_letter_pdf" if kind == "resume" else "resume_pdf"
    other_default = "Cover_Letter.pdf" if kind == "resume" else "Resume.pdf"
    if name == values.get(other, other_default):
        raise ValueError("Resume and cover-letter PDF filenames must be different.")
    return name


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["resume", "cover_letter"])
    parser.add_argument("--repository", type=Path, required=True)
    args = parser.parse_args()
    print(output_name(args.repository, args.kind))
