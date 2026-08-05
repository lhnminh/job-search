from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path


SECTION_RE = re.compile(r"\\section\{([^{}]+)\}")
ENTRY_COMMAND = "\\customcventry"
ITEM_RE = re.compile(r"(?m)^(?P<indent>[ \t]*)\\item(?:[ \t]+)?")


class ResumeParseError(ValueError):
    """Raised when the controlled LaTeX structure cannot be parsed safely."""


@dataclass(slots=True)
class Bullet:
    id: str
    entry_id: str
    section: str
    entry_title: str
    entry_subtitle: str
    index: int
    text: str
    body_start: int
    body_end: int
    raw_start: int
    raw_end: int
    is_metadata: bool = False


@dataclass(slots=True)
class Entry:
    id: str
    section: str
    title: str
    subtitle: str
    date: str
    command_start: int
    command_end: int
    content_start: int
    content_end: int
    itemize_end: int
    bullets: list[Bullet] = field(default_factory=list)


@dataclass(slots=True)
class ResumeDocument:
    source: str
    entries: list[Entry]

    @property
    def sections(self) -> list[str]:
        return list(dict.fromkeys(entry.section for entry in self.entries))

    def bullet(self, bullet_id: str) -> Bullet:
        for entry in self.entries:
            for bullet in entry.bullets:
                if bullet.id == bullet_id:
                    return bullet
        raise KeyError(f"Bullet not found: {bullet_id}")

    def entry(self, entry_id: str) -> Entry:
        for entry in self.entries:
            if entry.id == entry_id:
                return entry
        raise KeyError(f"Entry not found: {entry_id}")


def _skip_space(source: str, index: int) -> int:
    while index < len(source) and source[index].isspace():
        index += 1
    return index


def _balanced_group(source: str, index: int, opening: str = "{", closing: str = "}") -> tuple[int, int, int]:
    if index >= len(source) or source[index] != opening:
        raise ResumeParseError(f"Expected {opening!r} at offset {index}")
    depth = 0
    escaped = False
    for cursor in range(index, len(source)):
        char = source[cursor]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return index + 1, cursor, cursor + 1
    raise ResumeParseError(f"Unterminated {opening!r} group at offset {index}")


def _entry_arguments(source: str, command_start: int) -> list[tuple[int, int]]:
    cursor = command_start + len(ENTRY_COMMAND)
    cursor = _skip_space(source, cursor)
    if cursor < len(source) and source[cursor] == "[":
        _, _, cursor = _balanced_group(source, cursor, "[", "]")
    arguments: list[tuple[int, int]] = []
    for _ in range(4):
        cursor = _skip_space(source, cursor)
        start, end, cursor = _balanced_group(source, cursor)
        arguments.append((start, end))
    return arguments


def _section_before(source: str, offset: int) -> str:
    section = "Unsectioned"
    for match in SECTION_RE.finditer(source, 0, offset):
        section = tex_to_text(match.group(1))
    return section


def _stable_id(*parts: str) -> str:
    label = "-".join(slugify(part) for part in parts if part)
    return label or hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]


def parse_resume(source: str) -> ResumeDocument:
    entries: list[Entry] = []
    cursor = 0
    seen: dict[str, int] = {}
    while True:
        command_start = source.find(ENTRY_COMMAND, cursor)
        if command_start < 0:
            break
        try:
            arguments = _entry_arguments(source, command_start)
        except ResumeParseError:
            cursor = command_start + len(ENTRY_COMMAND)
            continue

        title = tex_to_text(source[slice(*arguments[0])])
        subtitle = tex_to_text(source[slice(*arguments[1])])
        date = tex_to_text(source[slice(*arguments[2])])
        section = _section_before(source, command_start)
        base_id = _stable_id(section, title, subtitle)
        seen[base_id] = seen.get(base_id, 0) + 1
        entry_id = base_id if seen[base_id] == 1 else f"{base_id}-{seen[base_id]}"

        content_start, content_end = arguments[3]
        content = source[content_start:content_end]
        begin_offset = content.find("\\begin{itemize}")
        end_offset = content.rfind("\\end{itemize}")
        bullets: list[Bullet] = []
        itemize_end = content_end
        if begin_offset >= 0 and end_offset > begin_offset:
            item_region_start = content_start + begin_offset + len("\\begin{itemize}")
            itemize_end = content_start + end_offset
            region = source[item_region_start:itemize_end]
            matches = list(ITEM_RE.finditer(region))
            for index, match in enumerate(matches):
                raw_start = item_region_start + match.start()
                body_start = item_region_start + match.end()
                raw_end = item_region_start + (matches[index + 1].start() if index + 1 < len(matches) else len(region))
                body_end = raw_end
                while body_end > body_start and source[body_end - 1].isspace():
                    body_end -= 1
                bullet_source = source[body_start:body_end].strip()
                display = tex_to_text(bullet_source)
                bullets.append(
                    Bullet(
                        id=f"{entry_id}:{index + 1}",
                        entry_id=entry_id,
                        section=section,
                        entry_title=title,
                        entry_subtitle=subtitle,
                        index=index + 1,
                        text=bullet_source,
                        body_start=body_start,
                        body_end=body_end,
                        raw_start=raw_start,
                        raw_end=raw_end,
                        is_metadata=display.lower().startswith(("technologies:", "technology:", "tools:")),
                    )
                )

        command_end = arguments[-1][1] + 1
        entries.append(
            Entry(
                id=entry_id,
                section=section,
                title=title,
                subtitle=subtitle,
                date=date,
                command_start=command_start,
                command_end=command_end,
                content_start=content_start,
                content_end=content_end,
                itemize_end=itemize_end,
                bullets=bullets,
            )
        )
        cursor = command_end
    if not entries:
        raise ResumeParseError("No \\customcventry entries were found")
    return ResumeDocument(source=source, entries=entries)


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


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    return normalized[:80]


def validate_slug(slug: str) -> list[str]:
    errors: list[str] = []
    if slug != slugify(slug) or not slug:
        errors.append("Folder slug must contain only lowercase letters, numbers, and hyphens")
    if slug in {"shared", "scripts", "src", "tests", "tmp", "output", ".", ".."}:
        errors.append(f"Reserved folder slug: {slug}")
    return errors


def replace_bullet(source: str, bullet_id: str, replacement: str) -> str:
    bullet = parse_resume(source).bullet(bullet_id)
    replacement = replacement.strip()
    if not replacement:
        raise ValueError("Replacement bullet cannot be empty")
    return source[: bullet.body_start] + replacement + source[bullet.body_end :]


def remove_bullet(source: str, bullet_id: str) -> str:
    bullet = parse_resume(source).bullet(bullet_id)
    return source[: bullet.raw_start] + source[bullet.raw_end :]


def prepare_interactive_tailored_source(source: str) -> str:
    """Create a compact working copy without changing factual resume content."""
    prepared = re.sub(r"(?m)^[ \t]*\\newpage[ \t]*\n?", "", source)
    prepared = prepared.replace(
        "\\documentclass[11pt,a4paper,sans]{moderncv}",
        "\\documentclass[10pt,a4paper,sans]{moderncv}",
        1,
    )
    prepared = prepared.replace("\\newcommand*{\\customcventry}[5][0.8em]", "\\newcommand*{\\customcventry}[5][0.45em]", 1)
    prepared = prepared.replace("\\fontsize{12}{12}", "\\fontsize{11.5}{11.5}")
    prepared = prepared.replace("\\par\\addvspace{0.15em}", "\\par\\addvspace{0.05em}")
    if "\\renewcommand{\\baselinestretch}" not in prepared:
        prepared = prepared.replace(
            "\\renewcommand{\\labelitemi}{\\textbullet}",
            "\\renewcommand{\\labelitemi}{\\textbullet}\n\\renewcommand{\\baselinestretch}{0.96}",
            1,
        )
    if "\\makecvtitle\n\\vspace" not in prepared:
        prepared = prepared.replace("\\makecvtitle % Print the CV title", "\\makecvtitle % Print the CV title\n\\vspace{-1.3em}", 1)
    return prepared


def apply_line_decisions(base_source: str, decisions: dict[str, dict[str, str]]) -> str:
    """Rebuild a draft from stable base offsets and explicit per-line decisions."""
    document = parse_resume(base_source)
    edits: list[tuple[int, int, str]] = []
    for entry in document.entries:
        for bullet in entry.bullets:
            decision = decisions.get(bullet.id)
            if not decision or decision.get("action") == "keep":
                continue
            if decision.get("action") == "remove":
                edits.append((bullet.raw_start, bullet.raw_end, ""))
                continue
            replacement = decision.get("text", "").strip()
            if replacement:
                edits.append((bullet.body_start, bullet.body_end, replacement))
    result = base_source
    for start, end, replacement in sorted(edits, reverse=True):
        result = result[:start] + replacement + result[end:]
    return result


def append_bullet(source: str, entry_id: str, bullet_text: str) -> str:
    document = parse_resume(source)
    entry = document.entry(entry_id)
    bullet_text = bullet_text.strip()
    if not bullet_text:
        raise ValueError("Appended bullet cannot be empty")
    normalized = tex_to_text(bullet_text).casefold()
    if any(tex_to_text(item.text).casefold() == normalized for item in entry.bullets):
        return source
    indent = "    "
    if entry.bullets:
        match = re.match(r"[ \t]*", source[entry.bullets[0].raw_start :])
        if match:
            indent = match.group(0)
    insertion_at = next((item.raw_start for item in entry.bullets if item.is_metadata), entry.itemize_end)
    insertion = f"{indent}\\item {bullet_text}\n"
    return source[:insertion_at] + insertion + source[insertion_at:]


def append_bullet_by_title(source: str, entry_title: str, bullet_text: str) -> str:
    document = parse_resume(source)
    wanted = tex_to_text(entry_title).casefold()
    matches = [entry for entry in document.entries if entry.title.casefold() == wanted]
    if not matches:
        raise KeyError(f"No root entry matches {entry_title!r}")
    if len(matches) > 1:
        raise KeyError(f"Multiple root entries match {entry_title!r}")
    return append_bullet(source, matches[0].id, bullet_text)


CLAIM_RE = re.compile(
    r"(?:\\?\$\s*\d+(?:\.\d+)?\s*[KMB]?)|(?:\b\d+(?:\.\d+)?\\?%)|"
    r"(?:\b\d+(?:\.\d+)?\+)|(?:\b\d+(?:\.\d+)?/\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


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
        root = parse_resume(root_source)
        proposed = parse_resume(proposed_source)
    except ResumeParseError as exc:
        errors.append(str(exc))
        return errors

    root_titles = {
        entry.title.casefold(): (entry.subtitle, entry.date)
        for entry in root.entries
        if "experience" in entry.section.casefold()
    }
    for entry in proposed.entries:
        if "experience" not in entry.section.casefold():
            continue
        expected = root_titles.get(entry.title.casefold())
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
        root_line = next((line.strip() for line in root_source.splitlines() if line.lstrip().startswith(f"\\{command}")), None)
        proposed_line = next(
            (line.strip() for line in proposed_source.splitlines() if line.lstrip().startswith(f"\\{command}")),
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
    """Require generated variants to retain every role and useful bullet depth."""
    try:
        root = parse_resume(root_source)
        proposed = parse_resume(proposed_source)
    except ResumeParseError as exc:
        return [str(exc)]

    proposed_experience = {
        entry.title.casefold(): entry
        for entry in proposed.entries
        if "experience" in entry.section.casefold()
    }
    errors: list[str] = []
    for root_entry in root.entries:
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


def validate_root_append_only(original_source: str, proposed_source: str) -> list[str]:
    """Verify that the candidate preserves the original bytes and parsed content in order."""
    errors: list[str] = []
    cursor = 0
    for char in proposed_source:
        if cursor < len(original_source) and char == original_source[cursor]:
            cursor += 1
    if cursor != len(original_source):
        errors.append("Root source contains a replacement or deletion; only insertions are allowed")
    try:
        original = parse_resume(original_source)
        proposed = parse_resume(proposed_source)
    except ResumeParseError as exc:
        errors.append(str(exc))
        return errors
    proposed_entries = {entry.id: entry for entry in proposed.entries}
    for entry in original.entries:
        candidate = proposed_entries.get(entry.id)
        if candidate is None:
            errors.append(f"Root entry was removed: {entry.title}")
            continue
        original_bullets = [item.text for item in entry.bullets]
        candidate_bullets = [item.text for item in candidate.bullets]
        position = 0
        for bullet in candidate_bullets:
            if position < len(original_bullets) and bullet == original_bullets[position]:
                position += 1
        if position != len(original_bullets):
            errors.append(f"An existing root bullet changed under {entry.title}")
    return errors


def source_hash(source: str) -> str:
    return hashlib.sha256(source.encode()).hexdigest()


def resume_path(repo_root: Path, target: str) -> Path:
    root = repo_root.resolve()
    path = root / "_resume.tex" if target in {"", ".", "root"} else (root / target / "_resume.tex").resolve()
    if path != root / "_resume.tex" and root not in path.parents:
        raise ValueError(f"Resume target must stay inside the repository: {target}")
    return path
