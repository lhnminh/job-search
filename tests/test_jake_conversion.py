from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

from convert_loc_to_jake import convert  # noqa: E402


class JakeConversionTests(unittest.TestCase):
    def test_converts_only_active_entries_and_normalizes_jake_style(self) -> None:
        source = r"""
\firstname{Morgan}
\familyname{Le}
\mobile{123}
\email{morgan@example.com}
\linkedin{https://linkedin.example}{linkedin.example}
\github{https://github.example}{github.example}
\title{\href{https://portfolio.example}{portfolio.example}}
\begin{document}
\section{Relevant Experience}
% {\customcventry{Commented Employer}{Commented Title}{January 2020 - Present}{}}
{\customcventry{Shopee}{Analyst}{June 2025 - June 2026}
{\begin{itemize}
  \item Improved processing by 20\%.
  \item {\bfseries Technologies:} Python
\end{itemize}}}
\end{document}
"""
        result = convert(source)
        self.assertNotIn("Commented Employer", result)
        self.assertIn("{Shopee}{Jun 2025 -- Jun 2026}", result)
        self.assertIn("{\\bfseries Technologies:} Python.", result)
        self.assertIn("\\documentclass[a4paper,11pt]{article}", result)
        self.assertIn("\\usepackage[empty]{fullpage}", result)
        self.assertIn("\\newcommand{\\resumeItemListStart}{\\begin{itemize}}", result)
        self.assertNotIn("\\usepackage{jakeresume}", result)


if __name__ == "__main__":
    unittest.main()
