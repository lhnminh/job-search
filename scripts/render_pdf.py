#!/usr/bin/env python3
"""Render a PDF page to a PNG image using sips (default on macOS) or pdftoppm (fallback)."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def render_pdf_to_png(pdf_path: Path, output_prefix: Path) -> Path | None:
    sips_bin = shutil.which("sips")
    pdftoppm_bin = shutil.which("pdftoppm")
    out_png = output_prefix.parent / f"{output_prefix.name}-1.png"
    out_png.parent.mkdir(parents=True, exist_ok=True)

    if sips_bin:
        cmd = [sips_bin, "-s", "format", "png", "-Z", "1600", str(pdf_path), "--out", str(out_png)]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return out_png
    elif pdftoppm_bin:
        cmd = [pdftoppm_bin, "-r", "120", "-png", str(pdf_path), str(output_prefix)]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return out_png
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="Path to PDF file")
    parser.add_argument("--output-prefix", "-o", type=Path, help="Output prefix path (default: <pdf_stem>)")
    args = parser.parse_args()

    if not args.pdf.is_file():
        print(f"Error: PDF not found: {args.pdf}", file=sys.stderr)
        return 1

    prefix = args.output_prefix or (args.pdf.parent / args.pdf.stem)
    out = render_pdf_to_png(args.pdf, prefix)
    if out and out.is_file():
        print(f"Rendered image: {out}")
        return 0
    else:
        print("Error: Failed to render PDF; renderer missing or failed.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
