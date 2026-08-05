from __future__ import annotations

import unittest
import shutil
import tempfile
from pathlib import Path

from resume_cli.build import build_resume, verify_pdf


REPO_ROOT = Path(__file__).resolve().parents[1]


class PdfVerificationTests(unittest.TestCase):
    def test_root_pdf_is_structurally_valid(self) -> None:
        report = verify_pdf(REPO_ROOT / "Morgan_Le_Resume.pdf")
        self.assertEqual(2, report.pages)
        self.assertTrue(report.a4)
        self.assertGreater(report.links, 0)
        self.assertTrue(all(count > 0 for count in report.extracted_characters))

    def test_existing_tailored_pdfs_are_one_page(self) -> None:
        for folder in ("finance-consulting", "macquarie-asset-management"):
            with self.subTest(folder=folder):
                report = verify_pdf(REPO_ROOT / folder / "Morgan_Le_Resume.pdf")
                self.assertEqual(1, report.pages)

    def test_builds_an_isolated_tailored_folder(self) -> None:
        temporary_root = REPO_ROOT / "tmp"
        temporary_root.mkdir(exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix="cli-build-", dir=temporary_root))
        try:
            shutil.copyfile(REPO_ROOT / "finance-consulting" / "_resume.tex", folder / "_resume.tex")
            result = build_resume(REPO_ROOT, str(folder.relative_to(REPO_ROOT)))
            self.assertEqual(1, result.report.pages)
            self.assertTrue((folder / "Morgan_Le_Resume.pdf").is_file())
            self.assertEqual({"_resume.tex", "Morgan_Le_Resume.pdf"}, {path.name for path in folder.iterdir()})
        finally:
            shutil.rmtree(folder, ignore_errors=True)
            try:
                temporary_root.rmdir()
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()
