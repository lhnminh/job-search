#!/usr/bin/env python3
"""Convert a Markdown cover letter into compile-ready LaTeX matching the repository template and Jake typography."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]
DATE_PATTERN = re.compile(
    r"^(?:Date:\s*)?((?:(?:" + "|".join(MONTHS) + r")\s+\d{1,2},?\s+\d{4})|(?:\d{1,2}\s+(?:" + "|".join(MONTHS) + r")\s+\d{4})|(?:\d{4}-\d{2}-\d{2})|(?:_{3,})|(?:\[Date[^\]]*\]))\s*$",
    re.IGNORECASE
)
CLOSING_PATTERN = re.compile(
    r"^(Sincerely|Best regards|Warm regards|Regards|Respectfully|Yours sincerely|Yours faithfully),?\s*$",
    re.IGNORECASE
)
OPENING_PATTERN = re.compile(r"^(Dear\s+[^,\n:]+)[,:]?\s*$", re.IGNORECASE)


@dataclass
class CoverLetter:
    name: str = "Your Name"
    contact_items: list[str] = field(default_factory=list)
    date: str = ""
    recipient_lines: list[str] = field(default_factory=list)
    opening: str = "Dear Hiring Team,"
    paragraphs: list[str] = field(default_factory=list)
    closing: str = "Sincerely,"
    signature: str = "Your Name"


def md_inline_to_latex(text: str) -> str:
    """Convert markdown formatting (links, bold, italics, special chars) to LaTeX."""
    links: list[tuple[str, str]] = []

    def save_link(match: re.Match[str]) -> str:
        links.append((match.group(1), match.group(2)))
        return f"\x00LNK{len(links)-1}\x00"

    # Save markdown links
    processed = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", save_link, text)

    # Escape LaTeX special chars: &, %, $, #, _
    for char in ["&", "%", "$", "#", "_"]:
        processed = processed.replace(char, f"\\{char}")

    # Bold: **text** -> \textbf{text}
    processed = re.sub(r"\*\*([^*]+)\*\*", r"\\textbf{\1}", processed)

    # Italics: *text* -> \textit{text}
    processed = re.sub(r"\*([^*]+)\*", r"\\textit{\1}", processed)

    # Restore links
    for index, (label, url) in enumerate(links):
        label_tex = md_inline_to_latex(label)
        processed = processed.replace(f"\x00LNK{index}\x00", f"\\href{{{url}}}{{{label_tex}}}")

    return processed


def contact_item_priority(item: str) -> int:
    """Return sorting priority for contact items to match Jake header layout."""
    item_lower = item.lower()
    if re.search(r"\d{3}[-\s\.]\d{3}[-\s\.]\d{4}", item):
        return 0  # Phone number first
    if "mailto:" in item_lower or "@" in item_lower:
        return 1  # Email second
    if "linkedin" in item_lower:
        return 2  # LinkedIn third
    if "github" in item_lower:
        return 3  # GitHub fourth
    return 4  # Personal website / portfolio last


def format_contact_item(item: str) -> str:
    """Format an individual contact item with proper Jake-style LaTeX hyperlink/underline."""
    item = item.strip()
    link_match = re.match(r"^\[([^\]]+)\]\(([^)]+)\)$", item)
    if link_match:
        label, url = link_match.group(1), link_match.group(2)
        return f"\\href{{{url}}}{{\\underline{{\\smash{{{label}}}}}}}"

    if "@" in item and not item.startswith("http"):
        # Email
        clean_email = item.replace("mailto:", "").strip()
        return f"\\href{{mailto:{clean_email}}}{{\\underline{{\\smash{{{clean_email}}}}}}}"

    if any(domain in item.lower() for domain in ["linkedin.com", "github.com", "http://", "https://", ".io", ".org"]):
        url = item if item.startswith("http") else f"https://{item}"
        label = item.replace("https://", "").replace("http://", "").rstrip("/")
        return f"\\href{{{url}}}{{\\underline{{\\smash{{{label}}}}}}}"

    # Plain text like phone number or location
    return md_inline_to_latex(item)


def parse_md_cover_letter(content: str) -> CoverLetter:
    """Parse format-neutral Markdown cover letter into a CoverLetter dataclass."""
    lines = [line.strip() for line in content.splitlines()]
    letter = CoverLetter()

    i = 0
    total = len(lines)

    # 1. Parse Name (# Name)
    while i < total and not lines[i]:
        i += 1
    if i < total and lines[i].startswith("#"):
        letter.name = lines[i].lstrip("#").strip()
        letter.signature = letter.name
        i += 1

    # 2. Parse Contact line(s) before Date / Recipient
    # Contact items can be separated by `|` or on lines before date/recipient
    while i < total:
        line = lines[i]
        if not line:
            i += 1
            continue

        # Check if we hit date or opening
        if DATE_PATTERN.match(line) or OPENING_PATTERN.match(line):
            break

        # Check if line looks like contact info or applicant address
        if "|" in line or "@" in line or any(k in line.lower() for k in ["linkedin", "github", ".edu", ".com"]):
            parts = [p.strip() for p in line.split("|") if p.strip()]
            for part in parts:
                letter.contact_items.append(format_contact_item(part))
            i += 1
        elif any(k in line.lower() for k in ["apt", "suite", "new york", "ny 100", "street", "st.", "ave", "road", "dr."]):
            # Applicant home address line - skip from recipient
            i += 1
        else:
            # Reached date or recipient block
            break

    # Sort contact items to canonical Jake order: phone, email, linkedin, website
    letter.contact_items = sorted(letter.contact_items, key=contact_item_priority)

    # 3. Parse Date (optional)
    while i < total and not lines[i]:
        i += 1

    while i < total:
        line = lines[i]
        if not line:
            i += 1
            continue
        if DATE_PATTERN.match(line):
            m = DATE_PATTERN.match(line)
            if m:
                letter.date = m.group(1).strip()
            i += 1
        elif line.lower().startswith("date:"):
            # e.g. Date: ____________________ or Date: September 10, 2026
            date_val = line.split(":", 1)[1].strip()
            letter.date = date_val
            i += 1
        else:
            break

    # 4. Parse Recipient block (lines before Opening)
    while i < total and not lines[i]:
        i += 1

    while i < total:
        line = lines[i]
        if not line:
            i += 1
            continue
        if OPENING_PATTERN.match(line):
            break
        # Guard against applicant address or date lines accidentally caught in recipient
        if any(k in line.lower() for k in ["apt", "date:"]) or DATE_PATTERN.match(line):
            i += 1
            continue
        letter.recipient_lines.append(md_inline_to_latex(line))
        i += 1

    # 5. Parse Opening / Salutation
    while i < total and not lines[i]:
        i += 1

    if i < total and OPENING_PATTERN.match(lines[i]):
        m = OPENING_PATTERN.match(lines[i])
        if m:
            salutation = m.group(1).strip()
            # Standardize punctuation to comma
            letter.opening = f"{salutation},"
        i += 1

    # 6. Parse Body Paragraphs and Closing
    current_para: list[str] = []
    while i < total:
        line = lines[i]

        if not line:
            if current_para:
                letter.paragraphs.append(" ".join(current_para))
                current_para = []
            i += 1
            continue

        # Check if closing reached
        if CLOSING_PATTERN.match(line):
            m = CLOSING_PATTERN.match(line)
            if m:
                letter.closing = f"{m.group(1).strip()},"
            i += 1
            # Next non-empty line may be signature
            while i < total and not lines[i]:
                i += 1
            if i < total and lines[i]:
                letter.signature = lines[i].strip()
                i += 1
            break

        current_para.append(line)
        i += 1

    if current_para:
        letter.paragraphs.append(" ".join(current_para))

    return letter


def find_placeholders(text: str) -> list[str]:
    """Identify unfilled bracketed placeholders or underscores in the text."""
    # Matches patterns like [Company Name], [specific problem...], ____
    bracket_placeholders = re.findall(r"\[([A-Za-z0-9_\s,\.\-—]+)\]", text)
    underscore_placeholders = re.findall(r"(_{3,})", text)
    
    # Filter out valid markdown links that might look like [text](url) - already removed if raw
    # We want things like [Company Name], [Position Title]
    placeholders = []
    for bp in bracket_placeholders:
        # If it's followed by `(` in text, it might be a markdown link, skip
        if f"[{bp}](" in text:
            continue
        placeholders.append(f"[{bp}]")
    placeholders.extend(underscore_placeholders)
    return placeholders


def render_latex_cover_letter(letter: CoverLetter) -> str:
    """Render a CoverLetter instance into standard LaTeX source matching Jake styling and Domino layout."""
    template = r"""% Cover letter adapted from templates/cover-letter/_cover_letter.tex
\documentclass[a4paper,11pt]{letter}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage[hidelinks]{hyperref}

% Fix LaTeX letter.cls rubber vertical centering so header position is locked to Domino reference
\makeatletter
\def\@texttop{}
\makeatother

% Margin controls inherited from the repository cover-letter template.
\topmargin=-1.251in
\textheight=9.6in
\oddsidemargin=0pt
\textwidth=6.5in

\begin{document}

\signature{<<<SIGNATURE>>>}
<<<DATE_LINE>>>\longindentation=0pt
\let\raggedleft\raggedright

\begin{letter}{<<<RECIPIENT>>>}

\begin{center}
    \textbf{\Huge \scshape <<<NAME>>>}\par
    \vspace{5pt}
    \hrule height 0.4pt
    \vspace{0pt}
    {\small <<<CONTACT_LINE>>>\par}
\end{center}
\vspace*{1.2in}

\opening{<<<OPENING>>>}

<<<BODY>>>

\closing{<<<CLOSING>>>}

\end{letter}

\end{document}
"""

    contact_line = " $|$\n    ".join(letter.contact_items) if letter.contact_items else ""

    # Terminate each line-break command before the next recipient line. This
    # prevents placeholder lines such as ``[Company Name]`` from being parsed
    # as the optional spacing argument to ``\\`` by LaTeX.
    recipient_text = " \\\\{}\n".join(letter.recipient_lines) if letter.recipient_lines else "Hiring Team"

    body_paras = []
    for para in letter.paragraphs:
        tex_para = md_inline_to_latex(para)
        body_paras.append(f"\\noindent {tex_para}")

    body_text = "\n\n".join(body_paras)

    date_line = f"\\date{{{md_inline_to_latex(letter.date)}}}\n" if letter.date else ""

    output = template.replace("<<<NAME>>>", letter.name)
    output = output.replace("<<<DATE_LINE>>>", date_line)
    output = output.replace("<<<CONTACT_LINE>>>", contact_line)
    output = output.replace("<<<RECIPIENT>>>", recipient_text)
    output = output.replace("<<<OPENING>>>", letter.opening)
    output = output.replace("<<<BODY>>>", body_text)
    output = output.replace("<<<CLOSING>>>", letter.closing)
    output = output.replace("<<<SIGNATURE>>>", letter.signature)

    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_pos", nargs="?", type=Path, help="Path to markdown cover letter (positional)")
    parser.add_argument("-i", "--input", type=Path, help="Path to markdown cover letter (flag)")
    parser.add_argument("-o", "--output", type=Path, help="Output .tex path (defaults to _cover_letter.tex in same dir)")
    parser.add_argument("-b", "--build", action="store_true", help="Build PDF using scripts/build_cover_letter.sh")
    parser.add_argument("--allow-placeholders", action="store_true", help="Allow compiling even if bracketed placeholders exist")
    args = parser.parse_args()

    input_file = args.input or args.input_pos
    if not input_file:
        print("Error: No input file specified.", file=sys.stderr)
        return 1

    if not input_file.is_file():
        print(f"Error: Input file {input_file} does not exist.", file=sys.stderr)
        return 1

    content = input_file.read_text(encoding="utf-8")

    # Check for placeholders
    placeholders = find_placeholders(content)
    if placeholders:
        print(f"Warning: Found {len(placeholders)} unfilled placeholder(s) in {input_file}:", file=sys.stderr)
        for p in placeholders[:10]:
            print(f"  - {p}", file=sys.stderr)
        if len(placeholders) > 10:
            print(f"  ... and {len(placeholders) - 10} more", file=sys.stderr)

        if args.build and not args.allow_placeholders:
            print("Error: Refusing to build PDF with unfilled placeholders. Use --allow-placeholders to force.", file=sys.stderr)
            return 1

    letter = parse_md_cover_letter(content)
    latex_output = render_latex_cover_letter(letter)

    output_path = args.output
    if output_path is None:
        output_path = input_file.parent / "_cover_letter.tex"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(latex_output, encoding="utf-8")
    print(f"Generated {output_path}")

    if args.build:
        folder = output_path.parent
        repo_root = Path(__file__).resolve().parents[1]
        try:
            rel_folder = str(folder.resolve().relative_to(repo_root))
        except ValueError:
            rel_folder = str(folder)
        cmd = ["./scripts/build_cover_letter.sh", rel_folder]
        print(f"Running: {' '.join(cmd)}")
        res = subprocess.run(cmd, cwd=repo_root)
        return res.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
