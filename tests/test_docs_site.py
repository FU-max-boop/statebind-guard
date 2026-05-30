import unittest
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DocsSiteTests(unittest.TestCase):
    def test_landing_page_links_product_surface(self):
        html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        self.assertIn("StateBind Guard v0.1.1", html)
        self.assertIn("Make coding-agent handoffs executable.", html)
        self.assertIn("assets/statebind_guard_demo.svg", html)
        self.assertIn("assets/statebind_social_preview.png", html)
        self.assertIn('property="og:image"', html)
        self.assertIn('name="twitter:card" content="summary_large_image"', html)
        self.assertIn("FU-max-boop/statebind-guard@v0.1.1", html)
        self.assertIn("statebind init", html)
        self.assertIn("https://github.com/FU-max-boop/statebind-guard/releases/tag/v0.1.1", html)

    def test_social_preview_png_has_expected_dimensions(self):
        png = (ROOT / "docs" / "assets" / "statebind_social_preview.png").read_bytes()
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", png[16:24])
        self.assertEqual((width, height), (1200, 630))

    def test_readme_points_to_project_page(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("https://fu-max-boop.github.io/statebind-guard/", readme)


if __name__ == "__main__":
    unittest.main()
