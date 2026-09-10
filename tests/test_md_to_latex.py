from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "scripts"))

from md_to_latex import parse_md_resume, render_jake, render_vmock, render_loc  # noqa: E402


SAMPLE_MD = """# Morgan Le

[morgan.hn.le@gmail.com](mailto:morgan.hn.le@gmail.com) | 347-774-6979 | [lhnminh.github.io](https://lhnminh.github.io/) | [linkedin.com/in/morganhle](https://www.linkedin.com/in/morganhle/)

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
    def test_every_premade_has_parseable_markdown(self) -> None:
        premade_root = REPOSITORY_ROOT / "pre-made"
        premade_directories = sorted(path for path in premade_root.iterdir() if path.is_dir())

        self.assertGreater(len(premade_directories), 0)
        for directory in premade_directories:
            with self.subTest(premade=directory.name):
                markdown_path = directory / "resume.md"
                self.assertTrue(markdown_path.is_file(), f"Missing {markdown_path}")

                resume = parse_md_resume(markdown_path.read_text(encoding="utf-8"))
                self.assertTrue(resume.name)
                self.assertTrue(resume.email)
                self.assertGreater(len(resume.sections), 0)
                self.assertTrue(all(section.entries for section in resume.sections))

    def test_parse_md_resume(self) -> None:
        resume = parse_md_resume(SAMPLE_MD)
        self.assertEqual("Morgan Le", resume.name)
        self.assertEqual("347-774-6979", resume.phone)
        self.assertEqual("morgan.hn.le@gmail.com", resume.email)
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
        self.assertIn(r"\href{https://www.sea.com/products/shopee}{Shopee}", jake_tex)
        self.assertIn(r"\$100K", jake_tex)
        self.assertIn(r"25\%", jake_tex)
        self.assertIn(r"Top 8\%", jake_tex)
        self.assertIn(r"\textbf{Technologies:} Python, SQL, Looker.", jake_tex)
        self.assertIn(r"\resumeProjectHeading", jake_tex)

    def test_render_vmock(self) -> None:
        resume = parse_md_resume(SAMPLE_MD)
        vmock_tex = render_vmock(resume)
        self.assertIn(r"\documentclass[a4paper,10pt]{article}", vmock_tex)
        self.assertIn(r"\href{https://www.sea.com/products/shopee}{Shopee}", vmock_tex)
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
