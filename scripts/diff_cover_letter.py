#!/usr/bin/env python3
"""Compare two cover_letter.md files and display a structured diff of changes."""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path


GREEN = "\033[32m"
RED = "\033[31m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
BOLD = "\033[1m"
RESET = "\033[0m"


def resolve_cl_path(path_str: str) -> Path:
    p = Path(path_str).resolve()
    if p.is_dir():
        candidate = p / "cover_letter.md"
        if candidate.exists():
            return candidate
    return p


def format_text(text: str, color: str, use_color: bool) -> str:
    if use_color:
        return f"{color}{text}{RESET}"
    return text


def diff_cover_letters(base_content: str, target_content: str, use_color: bool = True) -> str:
    base_lines = base_content.splitlines()
    target_lines = target_content.splitlines()

    diff = difflib.unified_diff(
        base_lines,
        target_lines,
        fromfile="Base Track",
        tofile="Tailored Application",
        lineterm=""
    )

    out = []
    for line in diff:
        if line.startswith("+++") or line.startswith("---"):
            out.append(format_text(line, BOLD, use_color))
        elif line.startswith("@@"):
            out.append(format_text(line, CYAN, use_color))
        elif line.startswith("+"):
            out.append(format_text(line, GREEN, use_color))
        elif line.startswith("-"):
            out.append(format_text(line, RED, use_color))
        else:
            out.append(line)

    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base", help="Path to base cover letter file or directory")
    parser.add_argument("target", help="Path to target cover letter file or directory")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")
    args = parser.parse_args()

    base_path = resolve_cl_path(args.base)
    target_path = resolve_cl_path(args.target)

    if not base_path.is_file():
        print(f"Error: Base file not found: {base_path}", file=sys.stderr)
        return 1
    if not target_path.is_file():
        print(f"Error: Target file not found: {target_path}", file=sys.stderr)
        return 1

    base_text = base_path.read_text(encoding="utf-8")
    target_text = target_path.read_text(encoding="utf-8")

    diff_str = diff_cover_letters(base_text, target_text, use_color=not args.no_color)
    if not diff_str.strip():
        print("No changes found between cover letters.")
    else:
        print(diff_str)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
