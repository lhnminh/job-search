from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader, PdfWriter


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

from normalize_pdf import (  # noqa: E402
    _repair_bfchar_ligatures,
    _repair_bfrange_ligatures,
    normalize_pdf,
)


class PdfNormalizationTests(unittest.TestCase):
    def test_expands_ligatures_in_unicode_font_maps(self) -> None:
        cmap = b"2 beginbfchar\n<007B> <FB000069>\n<007C> <00660069>\nendbfchar"
        repaired = _repair_bfchar_ligatures(cmap)
        self.assertIn(b"<007B> <006600660069>", repaired)
        self.assertIn(b"<007C> <00660069>", repaired)

    def test_expands_ligature_ranges_to_explicit_unicode_mappings(self) -> None:
        cmap = b"1 beginbfrange\n<1B> <1E> <FB00>\nendbfrange"
        repaired = _repair_bfrange_ligatures(cmap)
        self.assertIn(
            b"<1B> <1E> [<00660066> <00660069> <0066006C> <006600660069>]",
            repaired,
        )

    def test_writes_pdf_15_with_classic_cross_references(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.pdf"
            destination = root / "normalized.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=595.28, height=841.89)
            writer.pdf_header = "%PDF-1.7"
            writer.write(source)

            normalize_pdf(source, destination)

            reader = PdfReader(destination, strict=True)
            self.assertEqual("%PDF-1.5", reader.pdf_header)
            self.assertNotIn(b"/Type/XRef", destination.read_bytes())
            self.assertEqual(1, len(reader.pages))
            self.assertAlmostEqual(595.28, float(reader.pages[0].mediabox.width), places=2)
            self.assertAlmostEqual(841.89, float(reader.pages[0].mediabox.height), places=2)


if __name__ == "__main__":
    unittest.main()
