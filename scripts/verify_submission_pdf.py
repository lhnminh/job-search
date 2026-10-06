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


def verify_submission(path: Path) -> dict:
    report = verify_pdf(path)
    if report.pages != 1:
        raise ValueError(f"Submission PDF must be exactly one page; got {report.pages}")
    return asdict(report)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()
    try:
        report = verify_submission(args.pdf)
    except Exception as error:
        print(f"PDF verification failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
