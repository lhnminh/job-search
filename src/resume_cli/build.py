from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


class BuildError(RuntimeError):
    pass


class PdfRenderError(BuildError):
    """Raised when PDF pages cannot be rendered for visual QA."""


@dataclass(slots=True)
class PdfReport:
    path: Path
    pages: int
    a4: bool
    extracted_characters: list[int]
    links: int


@dataclass(slots=True)
class BuildResult:
    report: PdfReport
    output: str


def verify_pdf(path: Path) -> PdfReport:
    if not path.is_file():
        raise BuildError(f"Expected PDF was not created: {path}")
    reader = PdfReader(path)
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
    if not reader.pages:
        raise BuildError("PDF contains no pages")
    if not all(extracted):
        raise BuildError("At least one PDF page has no extractable text")
    if not a4:
        raise BuildError("PDF is not A4")
    if links == 0:
        raise BuildError("PDF contains no hyperlinks")
    return PdfReport(path=path, pages=len(reader.pages), a4=a4, extracted_characters=extracted, links=links)


def build_resume(repo_root: Path, target: str) -> BuildResult:
    command = [str(repo_root / "scripts" / "build_resume.sh")]
    output_dir = repo_root
    if target not in {"", ".", "root"}:
        command.append(target)
        output_dir = repo_root / target
    process = subprocess.run(command, cwd=repo_root, text=True, capture_output=True)
    combined = "\n".join(part for part in (process.stdout, process.stderr) if part).strip()
    if process.returncode:
        raise BuildError(combined or f"Build failed with exit code {process.returncode}")
    report = verify_pdf(output_dir / "Morgan_Le_Resume.pdf")
    return BuildResult(report=report, output=combined)


def render_pdf(path: Path, output_dir: Path) -> list[Path]:
    executable = shutil.which("pdftoppm")
    output_dir.mkdir(parents=True, exist_ok=True)
    if executable is not None:
        prefix = output_dir / "page"
        process = subprocess.run(
            [executable, "-png", "-r", "140", str(path), str(prefix)],
            text=True,
            capture_output=True,
        )
        if process.returncode:
            raise PdfRenderError(process.stderr.strip() or "Poppler failed to render PDF pages")
        images = sorted(output_dir.glob("page-*.png"))
        if images:
            return images

    try:
        import pymupdf
    except ImportError as exc:
        raise PdfRenderError(
            "PDF page rendering is unavailable. Run `uv sync`, or install Poppler with `brew install poppler`."
        ) from exc

    try:
        document = pymupdf.open(path)
        scale = 140 / 72
        matrix = pymupdf.Matrix(scale, scale)
        images: list[Path] = []
        for page_number, page in enumerate(document, start=1):
            image_path = output_dir / f"page-{page_number}.png"
            page.get_pixmap(matrix=matrix, alpha=False).save(image_path)
            images.append(image_path)
        document.close()
    except Exception as exc:
        raise PdfRenderError(f"PyMuPDF failed to render {path.name}: {exc}") from exc
    if not images:
        raise PdfRenderError(f"PDF renderer produced no page images for {path.name}")
    return images
