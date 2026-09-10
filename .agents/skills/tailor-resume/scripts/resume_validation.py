"""Deterministic LaTeX and PDF checks for tailored resumes."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader


SECTION_RE = re.compile(r"\\section\{([^{}]+)\}")
ENTRY_COMMAND = "\\customcventry"
JAKE_SUBHEADING_COMMAND = "\\resumeSubheading"
JAKE_PROJECT_COMMAND = "\\resumeProjectHeading"
ITEM_RE = re.compile(r"(?m)^(?P<indent>[ \t]*)\\item(?:[ \t]+)?")
CLAIM_RE = re.compile(
    r"(?:\\?\$\s*\d+(?:\.\d+)?\s*[KMB]?)|(?:\b\d+(?:\.\d+)?\\?%)|"
    r"(?:\b\d+(?:\.\d+)?\+)|(?:\b\d+(?:\.\d+)?/\d+(?:\.\d+)?)",
    re.IGNORECASE,
)
MASTER_SOURCE_RELATIVE_PATH = Path("master") / "resume.md"
PDF_COMPATIBILITY_HEADER = "%PDF-1.5"
PRESENTATION_LIGATURES = frozenset("\ufb00\ufb01\ufb02\ufb03\ufb04\ufb05\ufb06")


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


def _command_arguments(
    source: str,
    command_start: int,
    command: str,
    count: int,
) -> tuple[list[tuple[int, int]], int]:
    cursor = _skip_space(source, command_start + len(command))
    arguments: list[tuple[int, int]] = []
    for _ in range(count):
        cursor = _skip_space(source, cursor)
        start, end, cursor = _balanced_group(source, cursor)
        arguments.append((start, end))
    return arguments, cursor


def _strip_comments(source: str) -> str:
    active_lines: list[str] = []
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
        active_lines.append(line[:cut])
    return "\n".join(active_lines)


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


def _parse_moderncv_resume(source: str) -> list[Entry]:
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

    return entries


def _jake_bullets(source: str) -> list[Bullet]:
    bullets: list[Bullet] = []
    for match in re.finditer(r"\\resumeItem(?=\s*\{)", source):
        try:
            arguments, _ = _command_arguments(source, match.start(), "\\resumeItem", 1)
        except ResumeValidationError:
            continue
        bullet_source = source[slice(*arguments[0])].strip()
        display = tex_to_text(bullet_source)
        bullets.append(
            Bullet(
                text=bullet_source,
                is_metadata=display.lower().startswith(("technologies:", "technology:", "tools:")),
            )
        )
    return bullets


def _parse_jake_resume(source: str) -> list[Entry]:
    body = source.partition("\\begin{document}")[2] or source
    command_re = re.compile(r"\\(?:resumeSubheading|resumeProjectHeading)(?=\s*\{)")
    matches = list(command_re.finditer(body))
    entries: list[Entry] = []
    for index, match in enumerate(matches):
        command = match.group(0)
        count = 4 if command == JAKE_SUBHEADING_COMMAND else 2
        arguments, command_end = _command_arguments(body, match.start(), command, count)
        next_entry = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        next_section_match = SECTION_RE.search(body, command_end)
        next_section = next_section_match.start() if next_section_match else len(body)
        content_end = min(next_entry, next_section)
        if command == JAKE_SUBHEADING_COMMAND:
            title = tex_to_text(body[slice(*arguments[0])])
            date = tex_to_text(body[slice(*arguments[1])])
            subtitle = tex_to_text(body[slice(*arguments[2])])
        else:
            heading = tex_to_text(body[slice(*arguments[0])]).replace("$", "")
            parts = [part.strip() for part in heading.split("|", 1)]
            title = parts[0]
            subtitle = parts[1] if len(parts) > 1 else ""
            date = tex_to_text(body[slice(*arguments[1])])
        entries.append(
            Entry(
                section=_section_before(body, match.start()),
                title=title,
                subtitle=subtitle,
                date=date,
                bullets=_jake_bullets(body[command_end:content_end]),
            )
        )
    return entries


def _strip_markdown_formatting(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = text.replace("**", "").replace("*", "")
    return text.strip()


def _parse_markdown_resume(source: str) -> list[Entry]:
    entries: list[Entry] = []
    current_section = ""
    current_entry = None

    for line in source.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("## "):
            current_section = stripped[3:].strip()
            current_entry = None
            continue
        if stripped.startswith("### "):
            raw_header = stripped[4:].strip()
            parts = [_strip_markdown_formatting(p) for p in raw_header.split("|")]
            title = parts[0]
            subtitle = parts[1] if len(parts) > 1 else ""
            current_entry = Entry(
                section=current_section,
                title=title,
                subtitle=subtitle,
                date="",
                bullets=[],
            )
            entries.append(current_entry)
            continue
        if stripped.startswith("*") and stripped.endswith("*") and not stripped.startswith("*-"):
            date_val = stripped.strip("* ").strip()
            if current_entry and not current_entry.date:
                current_entry.date = date_val
            continue
        if stripped.startswith("- "):
            bullet_raw = stripped[2:].strip()
            is_meta = bool(
                re.match(r"^\*\*(?:Technologies|Technology|Tools):\*\*", bullet_raw, re.IGNORECASE)
            )
            if current_entry:
                current_entry.bullets.append(Bullet(text=bullet_raw, is_metadata=is_meta))
            continue

    return entries


def parse_resume(source: str) -> list[Entry]:
    if "# " in source and "\\begin{document}" not in source and "\\documentclass" not in source:
        entries = _parse_markdown_resume(source)
        if entries:
            return entries
    active = _strip_comments(source)
    entries = _parse_moderncv_resume(active)
    if not entries:
        entries = _parse_jake_resume(active)
    if not entries:
        raise ResumeValidationError(
            "No active \\customcventry, \\resumeSubheading, or \\resumeProjectHeading entries were found"
        )
    return entries


def _canonical_date(value: str) -> str:
    months = {
        "january": "jan",
        "february": "feb",
        "march": "mar",
        "april": "apr",
        "june": "jun",
        "july": "jul",
        "august": "aug",
        "september": "sep",
        "october": "oct",
        "november": "nov",
        "december": "dec",
    }
    normalized = value.casefold()
    for full, short in months.items():
        normalized = re.sub(rf"\b{full}\b", short, normalized)
    normalized = normalized.replace("–", "-")
    normalized = re.sub(r"\s*-+\s*", "-", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _contact_fields_markdown(source: str) -> dict[str, tuple[str, ...]]:
    fields: dict[str, tuple[str, ...]] = {}
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and "firstname" not in fields:
            name = stripped[2:].strip()
            parts = name.split(maxsplit=1)
            fields["firstname"] = (parts[0],)
            fields["familyname"] = (parts[1] if len(parts) > 1 else "",)
        elif "|" in stripped or "@" in stripped:
            items = [it.strip() for it in stripped.split("|")]
            for item in items:
                link_m = re.match(r"\[([^\]]+)\]\(([^)]+)\)", item)
                if link_m:
                    label, url = link_m.group(1), link_m.group(2)
                    if "mailto:" in url or "@" in label:
                        fields["email"] = (label,)
                    elif "linkedin.com" in url or "linkedin.com" in label:
                        fields["linkedin"] = (url, label)
                    elif "github.com" in url or "github.com" in label:
                        fields["github"] = (url, label)
                    else:
                        fields["website"] = (url, label)
                elif re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", item):
                    fields["mobile"] = (item,)
                elif "@" in item:
                    fields["email"] = (item,)
            break
    return fields


def _contact_fields(source: str) -> dict[str, tuple[str, ...]]:
    if "\\begin{document}" not in source and "\\documentclass" not in source:
        return _contact_fields_markdown(source)
    active = _strip_comments(source)
    marker = active.find("\\resumeContactHeader")
    if marker >= 0:
        arguments, _ = _command_arguments(active, marker, "\\resumeContactHeader", 9)
        values = [tex_to_text(active[slice(*argument)]) for argument in arguments]
        return {
            "firstname": (values[0],),
            "familyname": (values[1],),
            "mobile": (values[2],),
            "email": (values[3],),
            "linkedin": (values[4], values[5]),
            "github": (values[6], values[7]),
        }

    body = active.partition("\\begin{document}")[2] or active
    center_start = body.find("\\begin{center}")
    center_end = body.find("\\end{center}", center_start)
    if center_start >= 0 and center_end > center_start:
        header = body[center_start:center_end]
        name_marker = header.find("\\textbf")
        small_marker = header.find("\\small")
        separator = header.find("$|$", small_marker)
        if name_marker >= 0 and small_marker >= 0 and separator > small_marker:
            name_arguments, _ = _command_arguments(header, name_marker, "\\textbf", 1)
            name = tex_to_text(header[slice(*name_arguments[0])])
            name_parts = name.split(maxsplit=1)
            fields = {
                "firstname": (name_parts[0],),
                "familyname": (name_parts[1] if len(name_parts) > 1 else "",),
                "mobile": (tex_to_text(header[small_marker + len("\\small") : separator]),),
            }
            for link in re.finditer(r"\\href(?=\s*\{)", header):
                arguments, _ = _command_arguments(header, link.start(), "\\href", 2)
                url = tex_to_text(header[slice(*arguments[0])])
                label = tex_to_text(header[slice(*arguments[1])])
                if url.startswith("mailto:"):
                    fields["email"] = (url.removeprefix("mailto:"),)
                elif "linkedin.com" in url:
                    fields["linkedin"] = (url, label)
                elif "github.com" in url:
                    fields["github"] = (url, label)
                else:
                    fields["website"] = (url, label)
            if all(key in fields for key in ("email", "linkedin")):
                return fields

    fields: dict[str, tuple[str, ...]] = {}
    for command, count in (
        ("firstname", 1),
        ("familyname", 1),
        ("mobile", 1),
        ("email", 1),
        ("linkedin", 2),
        ("github", 2),
        ("homepage", 2),
    ):
        marker = active.find(f"\\{command}")
        if marker < 0:
            continue
        arguments, _ = _command_arguments(active, marker, f"\\{command}", count)
        fields[command] = tuple(tex_to_text(active[slice(*argument)]) for argument in arguments)
    if "homepage" in fields and "website" not in fields:
        fields["website"] = fields["homepage"]
    return fields


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
        if _canonical_date(expected_date) != _canonical_date(entry.date):
            errors.append(
                f"Historical dates changed for {entry.title}: expected {expected_date!r}, got {entry.date!r}"
            )

    root_contacts = _contact_fields(root_source)
    proposed_contacts = _contact_fields(proposed_source)
    for command in ("firstname", "familyname", "email", "linkedin"):
        if root_contacts.get(command) != proposed_contacts.get(command):
            errors.append(f"Contact field changed or is missing: \\{command}")
    root_mobile = root_contacts.get("mobile", ("",))[0] if root_contacts.get("mobile") else ""
    proposed_mobile = proposed_contacts.get("mobile", ("",))[0] if proposed_contacts.get("mobile") else ""
    if re.sub(r"\D", "", root_mobile) != re.sub(r"\D", "", proposed_mobile):
        errors.append("Contact field changed or is missing: \\mobile")
    if root_contacts.get("github") != proposed_contacts.get("github"):
        if root_contacts.get("github") or proposed_contacts.get("github"):
            errors.append(f"Contact field changed or is missing: \\github")
    if root_contacts.get("website") != proposed_contacts.get("website"):
        if root_contacts.get("website") or proposed_contacts.get("website"):
            errors.append(f"Contact field changed or is missing: website")

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
    reader = PdfReader(path, strict=True)
    if not reader.pages:
        raise ResumeValidationError("PDF contains no pages")

    if reader.pdf_header != PDF_COMPATIBILITY_HEADER:
        raise ResumeValidationError(
            f"PDF must use compatibility version 1.5; got {reader.pdf_header}"
        )
    if b"/Type/XRef" in path.read_bytes():
        raise ResumeValidationError("PDF must use a classic cross-reference table")

    page_text = [(page.extract_text() or "").strip() for page in reader.pages]
    extracted = [len(text) for text in page_text]
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
    found_ligatures = sorted(PRESENTATION_LIGATURES.intersection("".join(page_text)))
    if found_ligatures:
        codepoints = ", ".join(f"U+{ord(character):04X}" for character in found_ligatures)
        raise ResumeValidationError(
            f"PDF text contains ATS-hostile presentation ligatures: {codepoints}"
        )
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
    requested = (root / target).resolve()
    if not target or target in {".", "root", "master"} or requested == (root / "master").resolve():
        raise ResumeValidationError("Validator target must be a tailored resume folder, not master")
    direct_source = requested / "_resume.tex"
    default_jake_source = requested / "Jake" / "_resume.tex"
    source = (default_jake_source if not direct_source.is_file() and default_jake_source.is_file() else direct_source).resolve()
    master_source = (root / MASTER_SOURCE_RELATIVE_PATH).resolve()
    if root not in source.parents or source.parent == root:
        raise ResumeValidationError(f"Resume target must stay in a repository subfolder: {target}")
    if source == master_source:
        raise ResumeValidationError("Validator target must be a tailored resume folder, not master")
    return source
