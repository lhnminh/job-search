#!/usr/bin/env python3
"""Initialize private workspace folders without overwriting existing content."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def initialize(root: Path, source: Path) -> Path:
    if not source.is_file():
        raise ValueError(f"Resume input not found: {source}")
    destination = root / "master/resume.md"
    if destination.exists():
        raise ValueError("master/resume.md already exists; initialization will not overwrite it.")
    for directory in ("master", "pre-made", "applications", ".resume"):
        (root / directory).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--resume", type=Path, help="Your verified Markdown resume")
    inputs.add_argument("--example", action="store_true", help="Use the public sample for a demonstration")
    args = parser.parse_args()
    try:
        destination = initialize(ROOT, ROOT / "public/resume.md" if args.example else args.resume)
    except (OSError, ValueError) as error:
        print(f"Initialization failed: {error}")
        return 1
    print(f"Created private source: {destination}")
    if args.example:
        print("Demo only: replace sample facts with your own verified resume before applying.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
