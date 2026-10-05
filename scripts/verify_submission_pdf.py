#!/usr/bin/env python3
"""Check submission PDFs before builders replace the previous output."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".agents/skills/tailor-resume/scripts"))
from resume_validation import verify_pdf  # noqa: E402


def verify_submission(path: Path, *, allow_multiple_pages: bool = False) -> dict:
    report = verify_pdf(path)
    if not allow_multiple_pages and report.pages != 1:
        raise ValueError(f"Submission PDF must be exactly one page; got {report.pages}")
    return asdict(report)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--allow-multiple-pages", action="store_true", help="For internal previews only")
    args = parser.parse_args()
    try:
        report = verify_submission(args.pdf, allow_multiple_pages=args.allow_multiple_pages)
    except Exception as error:
        print(f"PDF verification failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
