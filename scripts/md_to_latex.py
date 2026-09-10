#!/usr/bin/env python3
"""Convert a Markdown resume into compile-ready LaTeX for Jake, Vmock, or Loc templates."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


MONTHS = {
    "January": "Jan",
    "February": "Feb",
    "March": "Mar",
    "April": "Apr",
    "June": "Jun",
    "July": "Jul",
    "August": "Aug",
    "September": "Sep",
    "October": "Oct",
    "November": "Nov",
    "December": "Dec",
}


@dataclass
class MdBullet:
    text: str
    is_metadata: bool = False


@dataclass
class MdEntry:
    title: str
    subtitle: str = ""
    location: str = ""
    date: str = ""
    bullets: list[MdBullet] = field(default_factory=list)


@dataclass
class MdSection:
    name: str
    entries: list[MdEntry] = field(default_factory=list)


@dataclass
class MdResume:
    name: str = ""
    phone: str = ""
    email: str = ""
    website: tuple[str, str] = ("", "")  # (label, url)
    github: tuple[str, str] = ("", "")
    linkedin: tuple[str, str] = ("", "")
    sections: list[MdSection] = field(default_factory=list)


def normalize_date(value: str, *, dash: str = " -- ") -> str:
    cleaned = value.strip("* ").strip()
    for full, short in MONTHS.items():
        cleaned = re.sub(rf"\b{full}\b", short, cleaned)
    # Replace en-dash, em-dash, or hyphens with target dash
    cleaned = re.sub(r"\s*[–—\-]+\s*", dash, cleaned)
    return cleaned


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


def parse_md_resume(md_content: str) -> MdResume:
    """Parse structured markdown resume into an MdResume object."""
    lines = md_content.splitlines()
    resume = MdResume()

    current_section: MdSection | None = None
    current_entry: MdEntry | None = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith("# ") and not resume.name:
            resume.name = stripped[2:].strip()
            continue

        # Header contact line
        if not resume.sections and ("|" in stripped or "@" in stripped):
            items = [item.strip() for item in stripped.split("|")]
            for item in items:
                link_match = re.match(r"\[([^\]]+)\]\(([^)]+)\)", item)
                if link_match:
                    label, url = link_match.group(1), link_match.group(2)
                    if "mailto:" in url or "@" in label:
                        resume.email = label
                    elif "github.com" in url or "github.com" in label:
                        resume.github = (label, url)
                    elif "linkedin.com" in url or "linkedin.com" in label:
                        resume.linkedin = (label, url)
                    else:
                        resume.website = (label, url)
                elif re.search(r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}", item):
                    resume.phone = item
                elif "@" in item:
                    resume.email = item
            continue

        # Section header: ## Section Name
        if stripped.startswith("## "):
            sec_name = stripped[3:].strip()
            current_section = MdSection(name=sec_name)
            resume.sections.append(current_section)
            current_entry = None
            continue

        # Entry header: ### Title | Subtitle | Location
        if stripped.startswith("### "):
            parts = [part.strip() for part in stripped[4:].split("|")]
            title = parts[0]
            subtitle = parts[1] if len(parts) > 1 else ""
            location = parts[2] if len(parts) > 2 else ""
            current_entry = MdEntry(title=title, subtitle=subtitle, location=location)
            if current_section is not None:
                current_section.entries.append(current_entry)
            continue

        # Date line: *Date*
        if stripped.startswith("*") and stripped.endswith("*") and not stripped.startswith("*-"):
            date_val = stripped.strip("* ").strip()
            if current_entry is not None and not current_entry.date:
                current_entry.date = date_val
            continue

        # Bullet point: - Bullet
        if stripped.startswith("- "):
            bullet_raw = stripped[2:].strip()
            is_meta = bool(
                re.match(r"^\*\*(?:Technologies|Technology|Tools):\*\*", bullet_raw, re.IGNORECASE)
            )
            if current_entry is not None:
                current_entry.bullets.append(MdBullet(text=bullet_raw, is_metadata=is_meta))
            continue

    return resume


def render_jake(resume: MdResume) -> str:
    """Render resume using the 11pt Jake template."""
    preamble = r"""\documentclass[a4paper,11pt]{article}

% Original Jake layout with parser-friendly Type 1 text fonts.
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\usepackage[empty]{fullpage}
\usepackage{titlesec}
\usepackage[usenames,dvipsnames]{color}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage[english]{babel}
\usepackage{tabularx}

\pagestyle{fancy}
\fancyhf{}
\fancyfoot{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}

\addtolength{\oddsidemargin}{-0.5in}
\addtolength{\evensidemargin}{-0.5in}
\addtolength{\textwidth}{1in}
\addtolength{\topmargin}{-.5in}
\addtolength{\textheight}{1.0in}

\urlstyle{same}
\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}

\titleformat{\section}{
  \vspace{-4pt}\scshape\raggedright\large
}{}{0em}{}[\color{black}\titlerule \vspace{-5pt}]

\newcommand{\resumeItem}[1]{
  \item\small{
    {#1 \vspace{-2pt}}
  }
}

\newcommand{\resumeSubheading}[4]{
  \vspace{-2pt}\item
    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}
      \textbf{#1} & #2 \\
      \textit{\small#3} & \textit{\small #4} \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeSubSubheading}[2]{
  \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \textit{\small#1} & \textit{\small #2} \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeProjectHeading}[2]{
  \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \small#1 & #2 \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeSubItem}[1]{\resumeItem{#1}\vspace{-4pt}}
\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}
\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in, label={}]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}"""

    # Contact line
    contacts = []
    if resume.phone:
        contacts.append(f"\\small {resume.phone}")
    if resume.email:
        contacts.append(f"\\href{{mailto:{resume.email}}}{{\\underline{{{resume.email}}}}}")
    if resume.linkedin[0]:
        url = resume.linkedin[1] or f"https://{resume.linkedin[0]}"
        contacts.append(f"\\href{{{url}}}{{\\underline{{{resume.linkedin[0]}}}}}")
    if resume.github[0]:
        url = resume.github[1] or f"https://{resume.github[0]}"
        contacts.append(f"\\href{{{url}}}{{\\underline{{{resume.github[0]}}}}}")
    if resume.website[0]:
        url = resume.website[1] or f"https://{resume.website[0]}"
        contacts.append(f"\\href{{{url}}}{{\\underline{{{resume.website[0]}}}}}")

    contact_str = " $|$\n    ".join(contacts)

    header = f"""\\begin{{document}}

\\begin{{center}}
    \\textbf{{\\Huge \\scshape {resume.name}}} \\\\ \\vspace{{1pt}}
    {contact_str}
\\end{{center}}"""

    sections_tex = []
    for section in resume.sections:
        sec_title = section.name
        is_project = "project" in sec_title.casefold()
        is_education = "education" in sec_title.casefold()

        sec_out = [f"\\section{{{md_inline_to_latex(sec_title)}}}", "\\resumeSubHeadingListStart"]
        for entry in section.entries:
            title_tex = md_inline_to_latex(entry.title)
            date_tex = md_inline_to_latex(normalize_date(entry.date, dash=" -- "))
            sub_tex = md_inline_to_latex(entry.subtitle)

            if is_project:
                heading = f"\\textbf{{{title_tex}}}"
                if sub_tex:
                    heading += f" $|$ \\emph{{{sub_tex}}}"
                sec_out.extend([
                    "  \\resumeProjectHeading",
                    f"    {{{heading}}}{{{date_tex}}}",
                ])
            else:
                loc_tex = md_inline_to_latex(entry.location)
                sec_out.extend([
                    "  \\resumeSubheading",
                    f"    {{{title_tex}}}{{{date_tex}}}",
                    f"    {{{sub_tex}}}{{{loc_tex}}}",
                ])

            if entry.bullets:
                sec_out.append("    \\resumeItemListStart")
                for bullet in entry.bullets:
                    b_tex = md_inline_to_latex(bullet.text)
                    if bullet.is_metadata and not b_tex.endswith("."):
                        b_tex += "."
                    sec_out.append(f"      \\resumeItem{{{b_tex}}}")
                sec_out.append("    \\resumeItemListEnd")

        sec_out.append("\\resumeSubHeadingListEnd")
        sections_tex.append("\n".join(sec_out))

    body = "\n\n".join(sections_tex)
    return f"{preamble}\n\n{header}\n\n{body}\n\n\\end{{document}}\n"


def render_vmock(resume: MdResume) -> str:
    """Render resume using the compact 10pt Vmock template."""
    preamble = r"""\documentclass[a4paper,10pt]{article}

% Force traditional Type 1 fonts for compatibility with legacy resume parsers.
\usepackage[T1]{fontenc}
\usepackage{lmodern}

\usepackage[
  top=0.55in,
  bottom=0.5in,
  left=0.5in,
  right=0.5in
]{geometry}

\usepackage{titlesec}
\usepackage[usenames,dvipsnames]{color}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage[english]{babel}
\usepackage{tabularx}

\pagestyle{fancy}
\fancyhf{}
\fancyfoot{}
\renewcommand{\headrulewidth}{0pt}
\renewcommand{\footrulewidth}{0pt}

\urlstyle{same}
\raggedbottom
\raggedright
\setlength{\tabcolsep}{0in}

\titleformat{\section}{
  \vspace{-5pt}\scshape\raggedright\large
}{}{0em}{}[\color{black}\titlerule \vspace{-6pt}]

\newcommand{\resumeItem}[1]{
  \item\small{{#1 \vspace{-2pt}}}
}

\newcommand{\resumeSubheading}[4]{
  \vspace{-2pt}\item
    \begin{tabular*}{0.97\textwidth}[t]{l@{\extracolsep{\fill}}r}
      \small\textbf{#1} & \small #2 \\
      \textit{\small #3} & \textit{\small #4} \\
    \end{tabular*}\vspace{-7pt}
}

\newcommand{\resumeProjectHeading}[2]{
  \item
    \begin{tabular*}{0.97\textwidth}{l@{\extracolsep{\fill}}r}
      \small #1 & \small #2 \\
    \end{tabular*}\vspace{-7pt}
}

\renewcommand\labelitemii{$\vcenter{\hbox{\tiny$\bullet$}}$}
\newcommand{\resumeSubHeadingListStart}{\begin{itemize}[leftmargin=0.15in,label={}]}
\newcommand{\resumeSubHeadingListEnd}{\end{itemize}}
\newcommand{\resumeItemListStart}{\begin{itemize}[leftmargin=0.22in]}
\newcommand{\resumeItemListEnd}{\end{itemize}\vspace{-5pt}}"""

    contacts = []
    if resume.phone:
        contacts.append(f"\\small {resume.phone}")
    if resume.email:
        contacts.append(f"\\href{{mailto:{resume.email}}}{{\\underline{{{resume.email}}}}}")
    if resume.linkedin[0]:
        url = resume.linkedin[1] or f"https://{resume.linkedin[0]}"
        contacts.append(f"\\href{{{url}}}{{\\underline{{{resume.linkedin[0]}}}}}")
    if resume.github[0]:
        url = resume.github[1] or f"https://{resume.github[0]}"
        contacts.append(f"\\href{{{url}}}{{\\underline{{{resume.github[0]}}}}}")
    if resume.website[0]:
        url = resume.website[1] or f"https://{resume.website[0]}"
        contacts.append(f"\\href{{{url}}}{{\\underline{{{resume.website[0]}}}}}")

    contact_str = " $|$\n  ".join(contacts)

    header = f"""\\begin{{document}}

\\begin{{center}}
  \\textbf{{\\Huge \\scshape {resume.name}}} \\\\ \\vspace{{2pt}}
  {contact_str}
\\end{{center}}"""

    sections_tex = []
    for section in resume.sections:
        sec_title = section.name
        is_project = "project" in sec_title.casefold()

        sec_out = [f"\\section{{{md_inline_to_latex(sec_title)}}}", "\\resumeSubHeadingListStart"]
        for entry in section.entries:
            title_tex = md_inline_to_latex(entry.title)
            date_tex = md_inline_to_latex(normalize_date(entry.date, dash=" -- "))
            sub_tex = md_inline_to_latex(entry.subtitle)

            if is_project:
                heading = f"\\textbf{{{title_tex}}}"
                if sub_tex:
                    heading += f" $|$ \\emph{{{sub_tex}}}"
                sec_out.extend([
                    "  \\resumeProjectHeading",
                    f"    {{{heading}}}{{{date_tex}}}",
                ])
            else:
                loc_tex = md_inline_to_latex(entry.location)
                sec_out.extend([
                    "  \\resumeSubheading",
                    f"    {{{title_tex}}}{{{date_tex}}}",
                    f"    {{{sub_tex}}}{{{loc_tex}}}",
                ])

            if entry.bullets:
                sec_out.append("    \\resumeItemListStart")
                for bullet in entry.bullets:
                    b_tex = md_inline_to_latex(bullet.text)
                    if bullet.is_metadata and not b_tex.endswith("."):
                        b_tex += "."
                    sec_out.append(f"      \\resumeItem{{{b_tex}}}")
                sec_out.append("    \\resumeItemListEnd")

        sec_out.append("\\resumeSubHeadingListEnd")
        sections_tex.append("\n".join(sec_out))

    body = "\n\n".join(sections_tex)
    return f"{preamble}\n\n{header}\n\n{body}\n\n\\end{{document}}\n"


def render_loc(resume: MdResume) -> str:
    """Render resume using the classic moderncv Loc template."""
    preamble = r"""\documentclass[11pt,a4paper,sans]{moderncv}

\moderncvstyle{classic}
\moderncvcolor{black}
\usepackage{multicol}
\usepackage{fontawesome}
\usepackage[scale=0.92]{geometry}

\renewcommand{\labelitemi}{\textbullet}

\newcommand*{\customcventry}[5][0.8em]{
  \begin{tabular}{@{}l}
    \fontsize{12}{12}{\bfseries #2}, {\itshape #3}
  \end{tabular}
  \hfill
  \begin{tabular}{l@{}}
    \fontsize{12}{12}{\itshape #4}
  \end{tabular}
  \ifx&#5&%
  \else{
    \par\addvspace{0.15em}
    \begin{minipage}{\maincolumnwidth}%
      #5%
    \end{minipage}}\fi%
  \par\addvspace{#1}}"""

    name_parts = resume.name.split(None, 1)
    firstname = name_parts[0] if name_parts else "Morgan"
    familyname = name_parts[1] if len(name_parts) > 1 else "Le"

    header_lines = [
        f"\\firstname{{{firstname}}}",
        f"\\familyname{{{familyname}}}",
    ]
    if resume.website[0]:
        url = resume.website[1] or f"https://{resume.website[0]}"
        header_lines.append(f"\\title{{\\href{{{url}}}{{{resume.website[0]}}}}}")
    if resume.phone:
        header_lines.append(f"\\mobile{{{resume.phone}}}")
    if resume.email:
        header_lines.append(f"\\email{{{resume.email}}}")
    if resume.github[0]:
        url = resume.github[1] or f"https://{resume.github[0]}"
        header_lines.append(f"\\github{{{url}}}{{{resume.github[0]}}}")
    if resume.linkedin[0]:
        url = resume.linkedin[1] or f"https://{resume.linkedin[0]}"
        header_lines.append(f"\\linkedin{{{url}}}{{{resume.linkedin[0]}}}")

    contact_block = "\n".join(header_lines)

    sections_tex = []
    for section in resume.sections:
        sec_title = section.name
        sec_out = [f"\\section{{{md_inline_to_latex(sec_title)}}}"]
        for entry in section.entries:
            title_tex = md_inline_to_latex(entry.title)
            date_tex = md_inline_to_latex(normalize_date(entry.date, dash=" - "))
            sub_tex = md_inline_to_latex(entry.subtitle)

            bullets_tex = ""
            if entry.bullets:
                b_lines = []
                for bullet in entry.bullets:
                    b_tex = md_inline_to_latex(bullet.text)
                    b_lines.append(f"    \\item {b_tex}")
                bullets_tex = "\\begin{itemize}\n" + "\n".join(b_lines) + "\n\\end{itemize}"

            entry_str = f"{{\\customcventry{{{title_tex}}}{{\\itshape {sub_tex}}}{{{date_tex}}}\n{{{bullets_tex}}}}}"
            sec_out.append(entry_str)

        sections_tex.append("\n\n".join(sec_out))

    body = "\n\n".join(sections_tex)
    return f"{preamble}\n\n{contact_block}\n\n\\begin{{document}}\n\n\\makecvtitle\n\n{body}\n\n\\end{{document}}\n"


RENDERERS = {
    "jake": render_jake,
    "vmock": render_vmock,
    "loc": render_loc,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_pos", nargs="?", type=Path, help="Path to markdown resume (positional)")
    parser.add_argument("-i", "--input", type=Path, help="Path to markdown resume (flag)")
    parser.add_argument("-t", "--template", choices=["jake", "vmock", "loc"], default="jake", help="Target template")
    parser.add_argument("-o", "--output", type=Path, help="Output .tex path")
    parser.add_argument("-b", "--build", action="store_true", help="Build PDF using build_resume.sh")
    args = parser.parse_args()

    input_file = args.input or args.input_pos or Path("master/resume.md")
    if not input_file.is_file():
        print(f"Error: Input file {input_file} does not exist.", file=sys.stderr)
        return 1

    content = input_file.read_text(encoding="utf-8")
    resume = parse_md_resume(content)
    renderer = RENDERERS[args.template.lower()]
    latex_output = renderer(resume)

    output_path = args.output
    if output_path is None:
        if args.build:
            if input_file.parent != Path("."):
                output_path = input_file.parent / "_resume.tex"
            else:
                output_path = Path("tmp/build_md") / "_resume.tex"
        else:
            sys.stdout.write(latex_output)
            return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(latex_output, encoding="utf-8")
    print(f"Generated {output_path} (format: {args.template})")

    if args.build:
        folder = output_path.parent
        repo_root = Path(__file__).resolve().parents[1]
        rel_folder = str(folder.resolve().relative_to(repo_root))
        cmd = ["./scripts/build_resume.sh", rel_folder]
        print(f"Running: {' '.join(cmd)}")
        res = subprocess.run(cmd, cwd=repo_root)
        return res.returncode

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
