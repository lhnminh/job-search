from __future__ import annotations

import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
from pypdf.annotations import Link

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import prepare_application as preparation
from verify_submission_pdf import verify_submission
from output_names import output_name


def fixture_pdf(path: Path, *, pages: int = 1, width: float = 595.28, text: bool = True) -> None:
    writer = PdfWriter()
    writer.pdf_header = "%PDF-1.5"
    for index in range(pages):
        page = writer.add_blank_page(width=width, height=841.89)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                                 NameObject("/Subtype"): NameObject("/Type1"),
                                 NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({
            NameObject("/F1"): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(b"BT /F1 12 Tf 50 700 Td (Example text) Tj ET" if text else b"")
        page[NameObject("/Contents")] = writer._add_object(stream)
        writer.add_annotation(index, Link(rect=(50, 690, 150, 710), url="https://example.com"))
    writer.write(path)


class SubmissionBuildTests(unittest.TestCase):
    def test_verifier_rejects_bad_submissions(self):
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / "fixture.pdf"
            for options in ({"pages": 2}, {"width": 612}, {"text": False}):
                fixture_pdf(pdf, **options)
                with self.assertRaises(ValueError):
                    verify_submission(pdf)
            pdf.write_bytes(b"corrupt")
            with self.assertRaises(Exception):
                verify_submission(pdf)

    def test_builders_preserve_previous_pdf_on_failure(self):
        (ROOT / ".resume").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / ".resume") as directory:
            folder = Path(directory)
            fixture = folder / "fixture.pdf"
            fake = folder / "tectonic"
            # bash is not needed in the fake compiler: source is always the last argument.
            fake.write_text('#!/bin/sh\nfor last; do :; done\ncp "$TEST_PDF" "${last%.tex}.pdf"\n')
            fake.chmod(0o755)
            env = dict(os.environ, RESUME_TECTONIC_BIN=str(fake),
                       RESUME_PYTHON_BIN=sys.executable, TEST_PDF=str(fixture))
            for kind, name in (("resume", output_name(ROOT, "resume")),
                               ("cover_letter", output_name(ROOT, "cover_letter"))):
                (folder / f"_{kind}.tex").write_text("fixture")
                output = folder / name
                for options in ({"pages": 2}, {"width": 612}, {"text": False}):
                    fixture_pdf(fixture, **options)
                    output.write_bytes(b"previous valid output")
                    result = subprocess.run([str(ROOT / f"scripts/build_{kind}.sh"),
                                             str(folder.relative_to(ROOT))], env=env,
                                            capture_output=True, text=True)
                    self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
                    self.assertEqual(b"previous valid output", output.read_bytes())
                fixture.write_bytes(b"corrupt")
                output.write_bytes(b"previous valid output")
                result = subprocess.run([str(ROOT / f"scripts/build_{kind}.sh"),
                                         str(folder.relative_to(ROOT))], env=env,
                                        capture_output=True, text=True)
                self.assertNotEqual(0, result.returncode)
                self.assertEqual(b"previous valid output", output.read_bytes())
                fixture_pdf(fixture)
                result = subprocess.run([str(ROOT / f"scripts/build_{kind}.sh"),
                                         str(folder.relative_to(ROOT))], env=env,
                                        capture_output=True, text=True)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                self.assertEqual(1, verify_submission(output)["pages"])

    def test_vmock_cli_rejected_before_writing(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/md_to_latex.py"),
                                 "--template", "vmock"], capture_output=True, text=True)
        self.assertEqual(2, result.returncode)
        self.assertIn("invalid choice", result.stderr)


class ApplicationPreparationTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("RESUME_PDF_INTEGRATION") == "1",
                         "set RESUME_PDF_INTEGRATION=1 for real PDF preparation")
    def test_real_combined_preparation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "master").mkdir()
            base = root / "pre-made/example"
            base.mkdir(parents=True)
            target = root / "applications/example"
            target.mkdir(parents=True)
            markdown = """# Sample Applicant

[email@example.com](mailto:email@example.com) | 212-555-0100

## Experience

### Example Company | Analyst | New York
*Jan 2024 – Present*
- Built reporting tools using Python.
- Improved data quality through automated checks.
"""
            letter = """# Sample Applicant

[email@example.com](mailto:email@example.com) | 212-555-0100

October 5, 2026

Example Company

Dear Hiring Team,

I am applying for the Analyst position at Example Company.

I built reporting tools using Python and improved data quality through automated checks.

I enjoy turning practical problems into reliable systems.

I welcome the opportunity to discuss my experience with your team.

Sincerely,
Sample Applicant
"""
            (root / "master/resume.md").write_text(markdown)
            for folder in (base, target):
                (folder / "resume.md").write_text(markdown)
                (folder / "cover_letter.md").write_text(letter)
            shutil.copytree(ROOT / "scripts", root / "scripts")
            shutil.copytree(ROOT / "shared", root / "shared")
            validators = root / ".agents/skills/tailor-resume/scripts"
            validators.mkdir(parents=True)
            shutil.copy2(ROOT / ".agents/skills/tailor-resume/scripts/resume_validation.py",
                         validators / "resume_validation.py")
            with patch.object(preparation, "ROOT", root), \
                 patch.dict(os.environ, {"RESUME_PYTHON_BIN": sys.executable}):
                review = preparation.prepare(target, {
                    "resume": base / "resume.md", "cover_letter": base / "cover_letter.md",
                }, [])
            for kind, filename in (("resume", "Resume.pdf"),
                                   ("cover_letter", "Cover_Letter.pdf")):
                self.assertEqual(1, verify_submission(target / filename)["pages"])
                self.assertTrue((review / f"{kind}-1.png").is_file())
                self.assertTrue((review / f"{kind}.diff").is_file())
            self.assertTrue((review / "report.json").is_file())

    def test_full_diff_keeps_distant_unchanged_context(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "base.md"
            target = Path(directory) / "target.md"
            content = "\n".join(f"Line {index}" for index in range(100))
            base.write_text(content)
            target.write_text(content.replace("Line 50", "Changed line"))
            diff = preparation.full_diff(base, target)
            for line in (" Line 0", "-Line 50", "+Changed line", " Line 99"):
                self.assertIn(line, diff)

    def test_failed_second_document_preserves_all_outputs_and_cleans_staging(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "applications/example"
            target.mkdir(parents=True)
            (root / "master").mkdir()
            (root / "master/resume.md").write_text("reference")
            bases = {}
            for kind in ("resume", "cover_letter"):
                base = root / f"{kind}.md"
                base.write_text("baseline")
                bases[kind] = base
                (target / f"{kind}.md").write_text("tailored")
                (target / f"_{kind}.tex").write_text("previous")
            def fake_run(command):
                if "--output" in command:
                    Path(command[command.index("--output") + 1]).write_text("generated")
                elif command[0].endswith("build_resume.sh"):
                    fixture_pdf(root / command[1] / "Resume.pdf")
                elif command[0] == "renderer":
                    Path(command[-1] + "-1.png").write_bytes(b"image")
                else:
                    raise ValueError("cover letter failed")
            with patch.object(preparation, "ROOT", root), \
                 patch.object(preparation.shutil, "which", return_value="renderer"), \
                 patch.object(preparation, "run", side_effect=fake_run), \
                 patch.object(preparation, "validate_tailored_tex", return_value=[]), \
                 patch.object(preparation, "validate_tailored_completeness", return_value=[]):
                with self.assertRaisesRegex(ValueError, "cover letter failed"):
                    preparation.prepare(target, bases, [])
            self.assertEqual([], list((root / ".resume/reviews").iterdir()))
            for kind in bases:
                self.assertEqual("previous", (target / f"_{kind}.tex").read_text())

    def test_baseline_rejects_application_inputs(self):
        with self.assertRaisesRegex(ValueError, "Baselines must"):
            preparation.baseline(str(ROOT / "applications/example/resume.md"), "resume.md")


if __name__ == "__main__":
    unittest.main()
