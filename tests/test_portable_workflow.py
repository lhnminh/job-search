from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from init_workspace import initialize
from output_names import output_name


class PortableWorkflowTests(unittest.TestCase):
    def test_initialization_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = ROOT / "tests/fixtures/resume.md"
            destination = initialize(root, source)
            self.assertEqual(source.read_text(), destination.read_text())
            with self.assertRaisesRegex(ValueError, "will not overwrite"):
                initialize(root, source)
            self.assertFalse((root / ".resume/settings.json").exists())

    def test_output_names_are_generic_and_local_overrides_are_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual("Resume.pdf", output_name(root, "resume"))
            self.assertEqual("Cover_Letter.pdf", output_name(root, "cover_letter"))
            (root / ".resume").mkdir()
            settings = root / ".resume/settings.json"
            settings.write_text(json.dumps({"resume_pdf": "Sample_Resume.pdf"}))
            self.assertEqual("Sample_Resume.pdf", output_name(root, "resume"))
            settings.write_text(json.dumps({"resume_pdf": "../public/private.pdf"}))
            with self.assertRaises(ValueError):
                output_name(root, "resume")

    def test_chat_markdown_converter_needs_no_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize(root, ROOT / "tests/fixtures/resume.md")
            output = root / "_resume.tex"
            result = subprocess.run([
                sys.executable, str(ROOT / "scripts/md_to_latex.py"),
                str(root / "master/resume.md"), "--template", "jake", "--output", str(output),
            ], capture_output=True, text=True)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn(r"\documentclass[a4paper,11pt]{article}", output.read_text())
            self.assertIn("Sample Applicant", output.read_text())
