#!/usr/bin/env python3
"""Check local prerequisites; never install software or access an AI provider."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]


def checks(root: Path) -> dict[str, bool]:
    return {
        "Python 3.12 or newer": sys.version_info >= (3, 12),
        "uv": bool(shutil.which("uv")),
        "Bash": bool(shutil.which("bash")),
        "Tectonic": bool(shutil.which("tectonic")),
        "Poppler (pdftoppm)": bool(shutil.which("pdftoppm")),
        "pypdf": importlib.util.find_spec("pypdf") is not None,
        "Private master/resume.md": (root / "master/resume.md").is_file(),
    }


if __name__ == "__main__":
    results = checks(ROOT)
    for label, ready in results.items():
        print(f"{'OK' if ready else 'MISSING'}: {label}")
    if not all(results.values()):
        print("Follow README.md setup instructions; no files or software were changed.")
    raise SystemExit(0 if all(results.values()) else 1)
