#!/usr/bin/env python3
"""Compare two resume.md files and display a structured diff of changes."""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

# Add parent directory to sys.path so we can import from scripts
sys.path.insert(0, str(Path(__file__).resolve().parent))
from md_to_latex import parse_md_resume, MdResume, MdSection, MdEntry


GREEN = "\033[32m"
RED = "\033[31m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
BOLD = "\033[1m"
RESET = "\033[0m"


def resolve_resume_path(path_str: str) -> Path:
    p = Path(path_str).resolve()
    if p.is_dir():
        candidate = p / "resume.md"
        if candidate.exists():
            return candidate
    return p


def format_text(text: str, color: str, use_color: bool) -> str:
    if use_color:
        return f"{color}{text}{RESET}"
    return text


def diff_bullets(base_bullets: list[str], target_bullets: list[str], use_color: bool) -> list[str]:
    lines: list[str] = []
    matcher = difflib.SequenceMatcher(None, base_bullets, target_bullets)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for b in base_bullets[i1:i2]:
                lines.append(f"    • {b}")
        elif tag == "delete":
            for b in base_bullets[i1:i2]:
                lines.append(format_text(f"  - • {b}", RED, use_color))
        elif tag == "insert":
            for b in target_bullets[j1:j2]:
                lines.append(format_text(f"  + • {b}", GREEN, use_color))
        elif tag == "replace":
            for b in base_bullets[i1:i2]:
                lines.append(format_text(f"  - • {b}", RED, use_color))
            for b in target_bullets[j1:j2]:
                lines.append(format_text(f"  + • {b}", GREEN, use_color))
    return lines


def structured_diff(base_res: MdResume, target_res: MdResume, use_color: bool) -> str:
    output: list[str] = []
    
    # Map sections by name
    base_secs = {s.name.lower(): s for s in base_res.sections}
    target_secs = {s.name.lower(): s for s in target_res.sections}
    all_sec_names = []
    for s in base_res.sections:
        if s.name.lower() not in all_sec_names:
            all_sec_names.append(s.name.lower())
    for s in target_secs.values():
        if s.name.lower() not in all_sec_names:
            all_sec_names.append(s.name.lower())

    stats = {"added_bullets": 0, "removed_bullets": 0, "modified_entries": 0}

    for sec_key in all_sec_names:
        b_sec = base_secs.get(sec_key)
        t_sec = target_secs.get(sec_key)
        sec_title = (t_sec or b_sec).name

        if b_sec is None and t_sec is not None:
            output.append(format_text(f"\n+ Section: {sec_title}", GREEN, use_color))
            for entry in t_sec.entries:
                output.append(format_text(f"  + [{entry.title}] {entry.subtitle}", GREEN, use_color))
                for b in entry.bullets:
                    output.append(format_text(f"    + • {b.text}", GREEN, use_color))
                    stats["added_bullets"] += 1
            continue

        if b_sec is not None and t_sec is None:
            output.append(format_text(f"\n- Section: {sec_title}", RED, use_color))
            for entry in b_sec.entries:
                output.append(format_text(f"  - [{entry.title}] {entry.subtitle}", RED, use_color))
                for b in entry.bullets:
                    output.append(format_text(f"    - • {b.text}", RED, use_color))
                    stats["removed_bullets"] += 1
            continue

        # Both exist - compare entries
        b_entries = {e.title.lower(): e for e in b_sec.entries}
        t_entries = {e.title.lower(): e for e in t_sec.entries}
        all_entry_keys = []
        for e in b_sec.entries:
            if e.title.lower() not in all_entry_keys:
                all_entry_keys.append(e.title.lower())
        for e in t_sec.entries:
            if e.title.lower() not in all_entry_keys:
                all_entry_keys.append(e.title.lower())

        sec_diff_lines: list[str] = []
        for e_key in all_entry_keys:
            b_entry = b_entries.get(e_key)
            t_entry = t_entries.get(e_key)

            if b_entry is None and t_entry is not None:
                stats["modified_entries"] += 1
                sec_diff_lines.append(format_text(f"  + Entry: {t_entry.title} | {t_entry.subtitle}", GREEN, use_color))
                for b in t_entry.bullets:
                    sec_diff_lines.append(format_text(f"    + • {b.text}", GREEN, use_color))
                    stats["added_bullets"] += 1
            elif b_entry is not None and t_entry is None:
                stats["modified_entries"] += 1
                sec_diff_lines.append(format_text(f"  - Entry: {b_entry.title} | {b_entry.subtitle}", RED, use_color))
                for b in b_entry.bullets:
                    sec_diff_lines.append(format_text(f"    - • {b.text}", RED, use_color))
                    stats["removed_bullets"] += 1
            else:
                # Both exist - check if bullets or subtitle differ
                b_b_texts = [b.text for b in b_entry.bullets]
                t_b_texts = [b.text for b in t_entry.bullets]
                sub_diff = b_entry.subtitle != t_entry.subtitle
                loc_diff = b_entry.location != t_entry.location
                date_diff = b_entry.date != t_entry.date
                bullets_differ = b_b_texts != t_b_texts

                if sub_diff or loc_diff or date_diff or bullets_differ:
                    stats["modified_entries"] += 1
                    sec_diff_lines.append(format_text(f"\n  ~ {t_entry.title} | {t_entry.subtitle}", CYAN, use_color))
                    bullet_diff_output = diff_bullets(b_b_texts, t_b_texts, use_color)
                    for line in bullet_diff_output:
                        if line.strip().startswith("- •"):
                            stats["removed_bullets"] += 1
                        elif line.strip().startswith("+ •"):
                            stats["added_bullets"] += 1
                    sec_diff_lines.extend(bullet_diff_output)

        if sec_diff_lines:
            output.append(format_text(f"\n## {sec_title}", BOLD, use_color))
            output.extend(sec_diff_lines)

    summary = format_text(
        f"\n--- Summary: +{stats['added_bullets']} bullets added, -{stats['removed_bullets']} bullets removed across {stats['modified_entries']} modified entries ---",
        YELLOW,
        use_color,
    )
    output.append(summary)
    return "\n".join(output)


def unified_text_diff(base_text: str, target_text: str, base_label: str, target_label: str, use_color: bool) -> str:
    base_lines = base_text.splitlines(keepends=True)
    target_lines = target_text.splitlines(keepends=True)
    diff = difflib.unified_diff(base_lines, target_lines, fromfile=base_label, tofile=target_label)
    
    out: list[str] = []
    for line in diff:
        line_clean = line.rstrip("\r\n")
        if line_clean.startswith("---") or line_clean.startswith("+++"):
            out.append(format_text(line_clean, BOLD, use_color))
        elif line_clean.startswith("@@"):
            out.append(format_text(line_clean, CYAN, use_color))
        elif line_clean.startswith("+"):
            out.append(format_text(line_clean, GREEN, use_color))
        elif line_clean.startswith("-"):
            out.append(format_text(line_clean, RED, use_color))
        else:
            out.append(line_clean)
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description="Diff two resume.md files or directories.")
    parser.add_argument("base", help="Path to base resume.md or directory")
    parser.add_argument("target", help="Path to target resume.md or directory")
    parser.add_argument("--unified", "-u", action="store_true", help="Show standard unified line diff")
    parser.add_argument("--no-color", action="store_true", help="Disable colored terminal output")
    args = parser.parse_args()

    base_path = resolve_resume_path(args.base)
    target_path = resolve_resume_path(args.target)

    if not base_path.exists():
        print(f"Error: Base file not found: {base_path}", file=sys.stderr)
        return 1
    if not target_path.exists():
        print(f"Error: Target file not found: {target_path}", file=sys.stderr)
        return 1

    use_color = sys.stdout.isatty() and not args.no_color

    base_text = base_path.read_text(encoding="utf-8")
    target_text = target_path.read_text(encoding="utf-8")

    if args.unified:
        print(unified_text_diff(base_text, target_text, str(base_path), str(target_path), use_color))
    else:
        base_res = parse_md_resume(base_text)
        target_res = parse_md_resume(target_text)
        print(structured_diff(base_res, target_res, use_color))

    return 0


if __name__ == "__main__":
    sys.exit(main())
