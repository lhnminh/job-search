#!/usr/bin/env python3
"""Convert one active moderncv premade source to the original Jake layout."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


SECTION_RE = re.compile(r"\\section\{([^{}]+)\}")
ENTRY_COMMAND = "\\customcventry"
ITEM_RE = re.compile(r"(?m)^[ \t]*\\item(?:[ \t]+)?")
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


JAKE_PREAMBLE = r"""\documentclass[a4paper,11pt]{article}

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


@dataclass
class RawEntry:
    title: str
    subtitle: str
    date: str
    content: str


def strip_comments(source: str) -> str:
    """Remove LaTeX comments while preserving escaped percent signs."""
    output: list[str] = []
    for line in source.splitlines():
        cut = len(line)
        for index, character in enumerate(line):
            if character != "%":
                continue
            backslashes = 0
            cursor = index - 1
            while cursor >= 0 and line[cursor] == "\\":
                backslashes += 1
                cursor -= 1
            if backslashes % 2 == 0:
                cut = index
                break
        output.append(line[:cut])
    return "\n".join(output)


def skip_space(source: str, index: int) -> int:
    while index < len(source) and source[index].isspace():
        index += 1
    return index


def balanced_group(source: str, index: int) -> tuple[str, int]:
    if index >= len(source) or source[index] != "{":
        raise ValueError(f"Expected '{{' at offset {index}")
    depth = 0
    escaped = False
    for cursor in range(index, len(source)):
        character = source[cursor]
        if escaped:
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return source[index + 1 : cursor], cursor + 1
    raise ValueError(f"Unterminated group at offset {index}")


def command_arguments(source: str, command: str, count: int, start: int = 0) -> tuple[list[str], int]:
    command_start = source.find(command, start)
    if command_start < 0:
        raise ValueError(f"Missing command: {command}")
    cursor = command_start + len(command)
    arguments: list[str] = []
    for _ in range(count):
        cursor = skip_space(source, cursor)
        argument, cursor = balanced_group(source, cursor)
        arguments.append(argument.strip())
    return arguments, cursor


def entries_in(section_source: str) -> list[RawEntry]:
    entries: list[RawEntry] = []
    cursor = 0
    while True:
        start = section_source.find(ENTRY_COMMAND, cursor)
        if start < 0:
            return entries
        arguments, cursor = command_arguments(section_source, ENTRY_COMMAND, 4, start)
        entries.append(RawEntry(*arguments))


def inline(value: str) -> str:
    value = re.sub(r"\\(?:itshape|bfseries|mdseries|small|normalsize)\b", "", value)
    return " ".join(value.split()).strip()


def plain(value: str) -> str:
    value = inline(value)
    value = re.sub(r"\\href\{[^{}]*\}\{([^{}]*)\}", r"\1", value)
    value = re.sub(r"\\text(?:bf|it)\{([^{}]*)\}", r"\1", value)
    value = value.replace("\\&", "&").replace("\\%", "%").replace("\\$", "$")
    value = re.sub(r"[{}]", "", value)
    return " ".join(value.split())


def normalized_date(value: str) -> str:
    value = inline(value)
    for full, short in MONTHS.items():
        value = re.sub(rf"\b{full}\b", short, value)
    return re.sub(r"\s+-+\s+", " -- ", value)


def bullets(content: str) -> list[str]:
    begin = content.find("\\begin{itemize}")
    end = content.rfind("\\end{itemize}")
    if begin < 0 or end <= begin:
        return []
    region = content[begin + len("\\begin{itemize}") : end]
    matches = list(ITEM_RE.finditer(region))
    output: list[str] = []
    for index, match in enumerate(matches):
        stop = matches[index + 1].start() if index + 1 < len(matches) else len(region)
        item = " ".join(region[match.end() : stop].split()).strip()
        if plain(item).lower().startswith(("technologies:", "technology:", "tools:")):
            if not plain(item).endswith("."):
                item += "."
        output.append(item)
    return output


def education_subtitle(entry: RawEntry) -> str:
    subtitle = inline(entry.subtitle)
    prefix = entry.content.partition("\\begin{itemize}")[0]
    minor = re.search(r"\\textit\{([^{}]+)\}", prefix)
    if minor:
        subtitle += "; " + inline(minor.group(1))
    return subtitle


def render_entry(entry: RawEntry, *, project: bool, education: bool) -> str:
    date = normalized_date(entry.date)
    output: list[str] = []
    if project:
        heading = f"\\textbf{{{inline(entry.title)}}}"
        subtitle = inline(entry.subtitle)
        if subtitle:
            heading += f" $|$ \\emph{{{subtitle}}}"
        output.extend(("  \\resumeProjectHeading", f"    {{{heading}}}{{{date}}}"))
    else:
        subtitle = education_subtitle(entry) if education else inline(entry.subtitle)
        output.extend(
            (
                "  \\resumeSubheading",
                f"    {{{inline(entry.title)}}}{{{date}}}",
                f"    {{{subtitle}}}{{}}",
            )
        )
    entry_bullets = bullets(entry.content)
    if entry_bullets:
        output.append("    \\resumeItemListStart")
        output.extend(f"      \\resumeItem{{{item}}}" for item in entry_bullets)
        output.append("    \\resumeItemListEnd")
    return "\n".join(output)


def contact_header(source: str) -> str:
    first = command_arguments(source, "\\firstname", 1)[0][0]
    family = command_arguments(source, "\\familyname", 1)[0][0]
    mobile = command_arguments(source, "\\mobile", 1)[0][0]
    email = command_arguments(source, "\\email", 1)[0][0]
    linkedin = command_arguments(source, "\\linkedin", 2)[0]
    github = command_arguments(source, "\\github", 2)[0]
    title = command_arguments(source, "\\title", 1)[0][0]
    return "\n".join(
        (
            "\\begin{center}",
            f"  \\textbf{{\\Huge \\scshape {first} {family}}} \\\\ \\vspace{{1pt}}",
            f"  \\small {mobile} $|$",
            f"  \\href{{mailto:{email}}}{{\\underline{{{email}}}}} $|$",
            f"  \\href{{{linkedin[0]}}}{{\\underline{{{linkedin[1]}}}}} $|$",
            f"  \\href{{{github[0]}}}{{\\underline{{{github[1]}}}}} $|$",
            f"  {title}",
            "\\end{center}",
        )
    )


def convert(source: str) -> str:
    active = strip_comments(source)
    body = active.partition("\\begin{document}")[2].partition("\\end{document}")[0]
    sections = list(SECTION_RE.finditer(body))
    if not sections:
        raise ValueError("The Loc source has no active sections")

    output = [
        "% Generated from the matching Loc source using the original Jake format.",
        JAKE_PREAMBLE,
        "",
        "\\begin{document}",
        "",
        contact_header(active),
        "",
    ]
    for index, section in enumerate(sections):
        stop = sections[index + 1].start() if index + 1 < len(sections) else len(body)
        name = inline(section.group(1))
        region = body[section.end() : stop]
        found_entries = entries_in(region)
        output.append(f"\\section{{{name}}}")
        if found_entries:
            is_project = "project" in plain(name).casefold()
            is_education = "education" in plain(name).casefold()
            output.append("\\resumeSubHeadingListStart")
            output.extend(
                render_entry(entry, project=is_project, education=is_education)
                for entry in found_entries
            )
            output.append("\\resumeSubHeadingListEnd")
        else:
            standalone = region.strip()
            if standalone:
                output.append(standalone)
        output.append("")
    output.extend(("\\end{document}", ""))
    return "\n".join(output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("loc_source", type=Path)
    parser.add_argument("jake_source", type=Path)
    arguments = parser.parse_args()
    converted = convert(arguments.loc_source.read_text(encoding="utf-8"))
    arguments.jake_source.parent.mkdir(parents=True, exist_ok=True)
    arguments.jake_source.write_text(converted, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
