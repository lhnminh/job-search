"""Deterministic LaTeX and PDF checks for tailored resumes."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader


SECTION_RE = re.compile(r"\\section\{([^{}]+)\}")
ENTRY_COMMAND = "\\customcventry"
ITEM_RE = re.compile(r"(?m)^(?P<indent>[ \t]*)\\item(?:[ \t]+)?")
CLAIM_RE = re.compile(
    r"(?:\\?\$\s*\d+(?:\.\d+)?\s*[KMB]?)|(?:\b\d+(?:\.\d+)?\\?%)|"
    r"(?:\b\d+(?:\.\d+)?\+)|(?:\b\d+(?:\.\d+)?/\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


class ResumeValidationError(ValueError):
    """Raised when a resume or PDF cannot be validated safely."""


@dataclass(slots=True)
class Bullet:
    text: str
    is_metadata: bool = False


@dataclass(slots=True)
class Entry:
    section: str
    title: str
    subtitle: str
    date: str
    bullets: list[Bullet] = field(default_factory=list)


@dataclass(slots=True)
class PdfReport:
    pages: int
    a4: bool
    extracted_characters: list[int]
    links: int


def _skip_space(source: str, index: int) -> int:
    while index < len(source) and source[index].isspace():
        index += 1
    return index


def _balanced_group(
    source: str,
    index: int,
    opening: str = "{",
    closing: str = "}",
) -> tuple[int, int, int]:
    if index >= len(source) or source[index] != opening:
        raise ResumeValidationError(f"Expected {opening!r} at offset {index}")
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
        if character == opening:
            depth += 1
        elif character == closing:
            depth -= 1
            if depth == 0:
                return index + 1, cursor, cursor + 1
    raise ResumeValidationError(f"Unterminated {opening!r} group at offset {index}")


def _entry_arguments(source: str, command_start: int) -> list[tuple[int, int]]:
    cursor = _skip_space(source, command_start + len(ENTRY_COMMAND))
    if cursor < len(source) and source[cursor] == "[":
        _, _, cursor = _balanced_group(source, cursor, "[", "]")
    arguments: list[tuple[int, int]] = []
    for _ in range(4):
        cursor = _skip_space(source, cursor)
        start, end, cursor = _balanced_group(source, cursor)
        arguments.append((start, end))
    return arguments


def tex_to_text(value: str) -> str:
    text = value
    href = re.compile(r"\\href\{[^{}]*\}\{([^{}]*)\}")
    while href.search(text):
        text = href.sub(r"\1", text)
    text = re.sub(r"\\(?:bfseries|itshape|mdseries|small|large|normalsize)\b", "", text)
    text = re.sub(r"\\text(?:bf|it)\{([^{}]*)\}", r"\1", text)
    text = text.replace("\\&", "&").replace("\\$", "$").replace("\\%", "%")
    text = text.replace("~", " ")
    text = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?", "", text)
    text = text.replace("{", "").replace("}", "")
    return " ".join(text.split())


def _section_before(source: str, offset: int) -> str:
    section = "Unsectioned"
    for match in SECTION_RE.finditer(source, 0, offset):
        section = tex_to_text(match.group(1))
    return section


def parse_resume(source: str) -> list[Entry]:
    entries: list[Entry] = []
    cursor = 0
    while True:
        command_start = source.find(ENTRY_COMMAND, cursor)
        if command_start < 0:
            break
        try:
            arguments = _entry_arguments(source, command_start)
        except ResumeValidationError:
            cursor = command_start + len(ENTRY_COMMAND)
            continue

        title = tex_to_text(source[slice(*arguments[0])])
        subtitle = tex_to_text(source[slice(*arguments[1])])
        date = tex_to_text(source[slice(*arguments[2])])
        content_start, content_end = arguments[3]
        content = source[content_start:content_end]
        begin_offset = content.find("\\begin{itemize}")
        end_offset = content.rfind("\\end{itemize}")
        bullets: list[Bullet] = []
        if begin_offset >= 0 and end_offset > begin_offset:
            region = content[begin_offset + len("\\begin{itemize}") : end_offset]
            matches = list(ITEM_RE.finditer(region))
            for index, match in enumerate(matches):
                body_end = matches[index + 1].start() if index + 1 < len(matches) else len(region)
                bullet_source = region[match.end() : body_end].strip()
                display = tex_to_text(bullet_source)
                bullets.append(
                    Bullet(
                        text=bullet_source,
                        is_metadata=display.lower().startswith(
                            ("technologies:", "technology:", "tools:")
                        ),
                    )
                )

        entries.append(
            Entry(
                section=_section_before(source, command_start),
                title=title,
                subtitle=subtitle,
                date=date,
                bullets=bullets,
            )
        )
        cursor = arguments[-1][1] + 1

    if not entries:
        raise ResumeValidationError("No \\customcventry entries were found")
    return entries


def numeric_claims(source: str) -> set[str]:
    body = source.partition("\\begin{document}")[2] or source
    return {re.sub(r"[\\\s]", "", match.group(0)).upper() for match in CLAIM_RE.finditer(body)}


def validate_tailored_tex(
    root_source: str,
    proposed_source: str,
    confirmed_facts: list[str] | tuple[str, ...] = (),
) -> list[str]:
    errors: list[str] = []
    if proposed_source.count("\\begin{document}") != 1 or proposed_source.count("\\end{document}") != 1:
        errors.append("Proposal must contain exactly one LaTeX document")
    try:
        root_entries = parse_resume(root_source)
        proposed_entries = parse_resume(proposed_source)
    except ResumeValidationError as error:
        errors.append(str(error))
        return errors

    root_experience = {
        entry.title.casefold(): (entry.subtitle, entry.date)
        for entry in root_entries
        if "experience" in entry.section.casefold()
    }
    for entry in proposed_entries:
        if "experience" not in entry.section.casefold():
            continue
        expected = root_experience.get(entry.title.casefold())
        if expected is None:
            errors.append(f"Unverified experience entry: {entry.title}")
            continue
        expected_title, expected_date = expected
        if expected_title.casefold() != entry.subtitle.casefold():
            errors.append(
                f"Historical title changed for {entry.title}: expected {expected_title!r}, got {entry.subtitle!r}"
            )
        if expected_date.casefold() != entry.date.casefold():
            errors.append(
                f"Historical dates changed for {entry.title}: expected {expected_date!r}, got {entry.date!r}"
            )

    for command in ("firstname", "familyname", "mobile", "email", "github", "linkedin"):
        root_line = next(
            (line.strip() for line in root_source.splitlines() if line.lstrip().startswith(f"\\{command}")),
            None,
        )
        proposed_line = next(
            (
                line.strip()
                for line in proposed_source.splitlines()
                if line.lstrip().startswith(f"\\{command}")
            ),
            None,
        )
        if root_line != proposed_line:
            errors.append(f"Contact field changed or is missing: \\{command}")

    verified_claims = numeric_claims(root_source + "\n" + "\n".join(confirmed_facts))
    extra_claims = numeric_claims(proposed_source) - verified_claims
    if extra_claims:
        errors.append("Unverified numeric claims: " + ", ".join(sorted(extra_claims)))
    return errors


def validate_tailored_completeness(root_source: str, proposed_source: str) -> list[str]:
    try:
        root_entries = parse_resume(root_source)
        proposed_entries = parse_resume(proposed_source)
    except ResumeValidationError as error:
        return [str(error)]

    proposed_experience = {
        entry.title.casefold(): entry
        for entry in proposed_entries
        if "experience" in entry.section.casefold()
    }
    errors: list[str] = []
    for root_entry in root_entries:
        if "experience" not in root_entry.section.casefold():
            continue
        proposed_entry = proposed_experience.get(root_entry.title.casefold())
        if proposed_entry is None:
            errors.append(f"Missing experience entry: {root_entry.title}")
            continue
        root_substantive = sum(not bullet.is_metadata for bullet in root_entry.bullets)
        proposed_substantive = sum(not bullet.is_metadata for bullet in proposed_entry.bullets)
        minimum = min(1, root_substantive)
        if proposed_substantive < minimum:
            errors.append(
                f"Too few substantive bullets for {root_entry.title}: expected at least {minimum}, got {proposed_substantive}"
            )
    return errors


def verify_pdf(path: Path) -> PdfReport:
    if not path.is_file():
        raise ResumeValidationError(f"Expected PDF was not created: {path}")
    reader = PdfReader(path)
    if not reader.pages:
        raise ResumeValidationError("PDF contains no pages")

    extracted = [len((page.extract_text() or "").strip()) for page in reader.pages]
    links = 0
    a4 = True
    for page in reader.pages:
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        a4 = a4 and abs(width - 595.28) < 2 and abs(height - 841.89) < 2
        for annotation in page.get("/Annots") or []:
            if annotation.get_object().get("/Subtype") == "/Link":
                links += 1

    if not all(extracted):
        raise ResumeValidationError("At least one PDF page has no extractable text")
    if not a4:
        raise ResumeValidationError("PDF is not A4")
    if links == 0:
        raise ResumeValidationError("PDF contains no hyperlinks")
    return PdfReport(
        pages=len(reader.pages),
        a4=a4,
        extracted_characters=extracted,
        links=links,
    )


def tailored_source_path(repository: Path, target: str) -> Path:
    root = repository.resolve()
    if not target or target in {".", "root"}:
        raise ResumeValidationError("Validator target must be a tailored resume folder")
    source = (root / target / "_resume.tex").resolve()
    if root not in source.parents or source.parent == root:
        raise ResumeValidationError(f"Resume target must stay in a repository subfolder: {target}")
    return source
