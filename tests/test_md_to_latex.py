from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

from md_to_latex import parse_md_resume, render_jake, render_vmock, render_loc  # noqa: E402


SAMPLE_MD = """# Sample Applicant

[email@example.com](mailto:email@example.com) | 212-555-0100 | [portfolio.example](https://example.com/) | [linkedin.com/in/your-profile](https://www.linkedin.com/in/your-profile/)

## Education

### Columbia University | Master's in Data Science | New York, NY
*August 2026 – Dec 2027*
- **GPA:** Incoming

## Relevant Experience

### [Shopee](https://www.sea.com/products/shopee) | Product Operations and Analytics Associate | Ho Chi Minh City, Vietnam
*Jun 2025 – Jun 2026*
- Applied statistical analysis, contributing to over $100K in revenue and 25% YoY growth.
- **Technologies:** Python, SQL, Looker

## Projects

### [Housing Prices Competition](https://github.com/lhnminh/Kaggle-Housing-Prices-Comp) | [Kaggle Competition](https://www.kaggle.com/competitions/home-data-for-ml-course/overview)
*Rank 403/5425 (Top 8%)*
- Built an end-to-end machine learning workflow to predict housing prices.
- **Technologies:** Python, scikit-learn, XGBoost
"""


class MdToLatexTests(unittest.TestCase):
    def test_public_resume_has_parseable_markdown(self) -> None:
        markdown_path = REPOSITORY_ROOT / "public" / "resume.md"
        self.assertTrue(markdown_path.is_file(), f"Missing {markdown_path}")

        resume = parse_md_resume(markdown_path.read_text(encoding="utf-8"))
        self.assertTrue(resume.name)
        self.assertTrue(resume.email)
        self.assertGreater(len(resume.sections), 0)
        self.assertTrue(all(section.entries for section in resume.sections))

    def test_parse_md_resume(self) -> None:
        resume = parse_md_resume(SAMPLE_MD)
        self.assertEqual("Sample Applicant", resume.name)
        self.assertEqual("212-555-0100", resume.phone)
        self.assertEqual("email@example.com", resume.email)
        self.assertEqual(3, len(resume.sections))
        self.assertEqual("Education", resume.sections[0].name)
        self.assertEqual("Relevant Experience", resume.sections[1].name)
        self.assertEqual("Projects", resume.sections[2].name)

        shopee = resume.sections[1].entries[0]
        self.assertEqual("[Shopee](https://www.sea.com/products/shopee)", shopee.title)
        self.assertEqual("Jun 2025 – Jun 2026", shopee.date)
        self.assertEqual(2, len(shopee.bullets))
        self.assertTrue(shopee.bullets[1].is_metadata)

    def test_render_jake(self) -> None:
        resume = parse_md_resume(SAMPLE_MD)
        jake_tex = render_jake(resume)
        self.assertIn(r"\documentclass[a4paper,11pt]{article}", jake_tex)
        self.assertIn(r"\href{mailto:email@example.com}{\underline{\smash{email@example.com}}}", jake_tex)
        self.assertIn(r"\href{https://www.linkedin.com/in/your-profile/}{\underline{\smash{linkedin.com/in/your-profile}}}", jake_tex)
        self.assertIn(r"\href{https://example.com/}{\underline{\smash{portfolio.example}}}", jake_tex)
        self.assertIn(r"\href{https://www.sea.com/products/shopee}{Shopee}", jake_tex)
        self.assertNotIn(r"\href{https://www.sea.com/products/shopee}{\underline{Shopee}}", jake_tex)
        self.assertIn(r"{#1\par\vspace{-2pt}}", jake_tex)
        self.assertNotIn(r"#1 \vspace{-2pt}", jake_tex)
        self.assertIn(r"\$100K", jake_tex)
        self.assertIn(r"25\%", jake_tex)
        self.assertIn(r"Top 8\%", jake_tex)
        self.assertIn(r"\textbf{Technologies:} Python, SQL, Looker.", jake_tex)
        self.assertIn(r"\resumeProjectHeading", jake_tex)

    def test_render_vmock(self) -> None:
        resume = parse_md_resume(SAMPLE_MD)
        vmock_tex = render_vmock(resume)
        self.assertIn(r"\documentclass[a4paper,10pt]{article}", vmock_tex)
        self.assertIn(r"\href{mailto:email@example.com}{\underline{\smash{email@example.com}}}", vmock_tex)
        self.assertIn(r"\href{https://www.linkedin.com/in/your-profile/}{\underline{\smash{linkedin.com/in/your-profile}}}", vmock_tex)
        self.assertIn(r"\href{https://example.com/}{\underline{\smash{portfolio.example}}}", vmock_tex)
        self.assertIn(r"\href{https://www.sea.com/products/shopee}{Shopee}", vmock_tex)
        self.assertNotIn(r"\href{https://www.sea.com/products/shopee}{\underline{Shopee}}", vmock_tex)
        self.assertIn(r"{#1\par\vspace{-2pt}}", vmock_tex)
        self.assertNotIn(r"#1 \vspace{-2pt}", vmock_tex)
        self.assertIn(r"\$100K", vmock_tex)
        self.assertIn(r"Top 8\%", vmock_tex)

    def test_render_loc(self) -> None:
        resume = parse_md_resume(SAMPLE_MD)
        loc_tex = render_loc(resume)
        self.assertIn(r"\documentclass[11pt,a4paper,sans]{moderncv}", loc_tex)
        self.assertIn(r"\customcventry", loc_tex)
        self.assertIn(r"\$100K", loc_tex)


if __name__ == "__main__":
    unittest.main()
