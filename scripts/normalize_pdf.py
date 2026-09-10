#!/usr/bin/env python3
"""Rewrite a PDF into the conservative structure used for resume uploads."""

from __future__ import annotations

import argparse
import os
import re
import tempfile
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject


PDF_HEADER = "%PDF-1.5"
PRESENTATION_LIGATURES = frozenset("\ufb00\ufb01\ufb02\ufb03\ufb04\ufb05\ufb06")
LIGATURE_EXPANSIONS = {
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
    "\ufb05": "st",
    "\ufb06": "st",
}
BFCHAR_BLOCK_RE = re.compile(rb"\d+\s+beginbfchar(?P<body>.*?)endbfchar", re.DOTALL)
BFCHAR_MAPPING_RE = re.compile(rb"(?P<source><[0-9A-Fa-f]+>\s+)<(?P<target>[0-9A-Fa-f]+)>")
BFRANGE_BLOCK_RE = re.compile(rb"\d+\s+beginbfrange(?P<body>.*?)endbfrange", re.DOTALL)
BFRANGE_MAPPING_RE = re.compile(
    rb"(?P<start><(?P<start_hex>[0-9A-Fa-f]+)>\s+)"
    rb"(?P<end><(?P<end_hex>[0-9A-Fa-f]+)>\s+)"
    rb"<(?P<target_hex>[0-9A-Fa-f]+)>"
)


def _page_text(reader: PdfReader) -> list[str]:
    return [page.extract_text() or "" for page in reader.pages]


def _page_sizes(reader: PdfReader) -> list[tuple[float, float]]:
    return [
        (float(page.mediabox.width), float(page.mediabox.height))
        for page in reader.pages
    ]


def _link_targets(reader: PdfReader) -> list[str]:
    targets: list[str] = []
    for page in reader.pages:
        annotations = page.get("/Annots")
        if not annotations:
            continue
        for reference in annotations.get_object():
            annotation = reference.get_object()
            if annotation.get("/Subtype") != "/Link":
                continue
            action = annotation.get("/A")
            if action:
                uri = action.get_object().get("/URI")
                if uri is not None:
                    targets.append(str(uri))
    return targets


def _expand_ligatures(text: str) -> str:
    return "".join(LIGATURE_EXPANSIONS.get(character, character) for character in text)


def _repair_bfchar_ligatures(cmap_data: bytes) -> bytes:
    def repair_block(block_match: re.Match[bytes]) -> bytes:
        block = block_match.group(0)

        def repair_mapping(mapping_match: re.Match[bytes]) -> bytes:
            target_hex = mapping_match.group("target")
            try:
                target = bytes.fromhex(target_hex.decode("ascii")).decode("utf-16-be")
            except (UnicodeDecodeError, ValueError):
                return mapping_match.group(0)
            expanded = _expand_ligatures(target)
            if expanded == target:
                return mapping_match.group(0)
            replacement = expanded.encode("utf-16-be").hex().upper().encode("ascii")
            return mapping_match.group("source") + b"<" + replacement + b">"

        return BFCHAR_MAPPING_RE.sub(repair_mapping, block)

    return BFCHAR_BLOCK_RE.sub(repair_block, cmap_data)


def _repair_bfrange_ligatures(cmap_data: bytes) -> bytes:
    def repair_block(block_match: re.Match[bytes]) -> bytes:
        block = block_match.group(0)

        def repair_mapping(mapping_match: re.Match[bytes]) -> bytes:
            start_hex = mapping_match.group("start_hex")
            end_hex = mapping_match.group("end_hex")
            target_hex = mapping_match.group("target_hex")
            start = int(start_hex, 16)
            end = int(end_hex, 16)
            target = int(target_hex, 16)
            width = len(target_hex)
            replacements: list[bytes] = []
            changed = False
            for offset in range(end - start + 1):
                encoded = (target + offset).to_bytes(width // 2, "big")
                try:
                    character = encoded.decode("utf-16-be")
                except UnicodeDecodeError:
                    return mapping_match.group(0)
                expanded = _expand_ligatures(character)
                changed = changed or expanded != character
                replacements.append(
                    b"<" + expanded.encode("utf-16-be").hex().upper().encode("ascii") + b">"
                )
            if not changed:
                return mapping_match.group(0)
            return (
                mapping_match.group("start")
                + mapping_match.group("end")
                + b"["
                + b" ".join(replacements)
                + b"]"
            )

        return BFRANGE_MAPPING_RE.sub(repair_mapping, block)

    return BFRANGE_BLOCK_RE.sub(repair_block, cmap_data)


def _repair_to_unicode_maps(writer: PdfWriter) -> int:
    repaired = 0
    visited_fonts: set[int] = set()
    for page in writer.pages:
        resources = page["/Resources"].get_object()
        font_resources = resources.get("/Font")
        if font_resources is None:
            continue
        fonts = font_resources.get_object()
        for font_reference in fonts.values():
            font = font_reference.get_object()
            font_id = font_reference.idnum if hasattr(font_reference, "idnum") else id(font)
            if font_id in visited_fonts:
                continue
            visited_fonts.add(font_id)
            cmap_reference = font.get("/ToUnicode")
            if cmap_reference is None:
                continue
            cmap_data = cmap_reference.get_object().get_data()
            repaired_data = _repair_bfchar_ligatures(cmap_data)
            repaired_data = _repair_bfrange_ligatures(repaired_data)
            if repaired_data == cmap_data:
                continue
            repaired_stream = DecodedStreamObject()
            repaired_stream.set_data(repaired_data)
            font[NameObject("/ToUnicode")] = writer._add_object(repaired_stream)
            repaired += 1
    return repaired


def _compatibility_errors(path: Path, reader: PdfReader) -> list[str]:
    errors: list[str] = []
    data = path.read_bytes()
    if reader.pdf_header != PDF_HEADER:
        errors.append(f"expected {PDF_HEADER}, got {reader.pdf_header}")
    if b"/Type/XRef" in data:
        errors.append("compressed cross-reference stream is still present")
    extracted_text = "".join(_page_text(reader))
    found_ligatures = sorted(PRESENTATION_LIGATURES.intersection(extracted_text))
    if found_ligatures:
        codepoints = ", ".join(f"U+{ord(character):04X}" for character in found_ligatures)
        errors.append(f"presentation-form ligatures remain in extracted text: {codepoints}")
    return errors


def normalize_pdf(source: Path, destination: Path) -> None:
    source = source.resolve()
    destination = destination.resolve()
    original = PdfReader(source, strict=True)
    original_text = [_expand_ligatures(text) for text in _page_text(original)]
    original_sizes = _page_sizes(original)
    original_links = _link_targets(original)

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{destination.stem}.",
            suffix=".pdf",
            dir=destination.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)

        writer = PdfWriter(clone_from=original)
        writer.pdf_header = PDF_HEADER
        _repair_to_unicode_maps(writer)
        writer.write(temporary_path)

        normalized = PdfReader(temporary_path, strict=True)
        errors = _compatibility_errors(temporary_path, normalized)
        if _page_text(normalized) != original_text:
            errors.append("extracted text changed during normalization")
        if _page_sizes(normalized) != original_sizes:
            errors.append("page geometry changed during normalization")
        if _link_targets(normalized) != original_links:
            errors.append("hyperlink targets changed during normalization")
        if errors:
            raise ValueError("PDF compatibility validation failed: " + "; ".join(errors))

        os.replace(temporary_path, destination)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    arguments = parser.parse_args()
    normalize_pdf(arguments.source, arguments.destination)
    print(f"Normalized {arguments.destination} as PDF 1.5 with classic cross-references")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
