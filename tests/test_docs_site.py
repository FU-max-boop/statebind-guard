import unittest
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DocsSiteTests(unittest.TestCase):
    def test_landing_page_links_product_surface(self):
        html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        self.assertIn("StateBind Guard v0.1.11", html)
        self.assertIn("Make coding-agent handoffs executable.", html)
        self.assertIn("assets/statebind_guard_demo.svg", html)
        self.assertIn("assets/statebind_social_preview.png", html)
        self.assertIn('property="og:image"', html)
        self.assertIn('name="twitter:card" content="summary_large_image"', html)
        self.assertIn("FU-max-boop/statebind-guard@v0.1.11", html)
        self.assertIn("statebind proof", html)
        self.assertIn("statebind init", html)
        self.assertIn("statebind install-hook", html)
        self.assertIn("statebind doctor", html)
        self.assertIn("Policy-as-code", html)
        self.assertIn("Launch package", html)
        self.assertIn("Launch-ready package", html)
        self.assertIn("Markdown summaries", html)
        self.assertIn("HTML reports", html)
        self.assertIn("GitHub annotations", html)
        self.assertIn("action outputs", html)
        self.assertIn("https://github.com/FU-max-boop/statebind-guard/releases/tag/v0.1.11", html)
        self.assertIn("docs/launch_note.md", html)
        self.assertIn("docs/launch_package.md", html)
        self.assertIn("docs/pre_commit_usage.md", html)
        self.assertIn("docs/policy_usage.md", html)

    def test_social_preview_png_has_expected_dimensions(self):
        png = (ROOT / "docs" / "assets" / "statebind_social_preview.png").read_bytes()
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", png[16:24])
        self.assertEqual((width, height), (1200, 630))

    def test_readme_points_to_project_page(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("https://fu-max-boop.github.io/statebind-guard/", readme)
        self.assertIn("docs/launch_note.md", readme)
        self.assertIn("docs/launch_package.md", readme)
        self.assertIn("docs/pre_commit_usage.md", readme)
        self.assertIn("docs/policy_usage.md", readme)
        self.assertIn("statebind install-hook", readme)
        self.assertIn("statebind doctor", readme)
        self.assertIn("statebind policy", readme)
        self.assertIn("statebind proof", readme)
        self.assertIn("bad_visible_unbound: FAIL", readme)
        self.assertIn("good_role_bound: PASS", readme)
        self.assertIn("actions/workflows/smoke.yml/badge.svg", readme)

    def test_launch_package_contains_outreach_material(self):
        package = (ROOT / "docs" / "launch_package.md").read_text(encoding="utf-8")
        self.assertIn("One-Liner", package)
        self.assertIn("Maintainer Pitch", package)
        self.assertIn("Launch Post", package)
        self.assertIn("statebind proof", package)
        self.assertIn("bad_visible_unbound: FAIL", package)
        self.assertIn("good_role_bound: PASS", package)
        self.assertIn("Technical Claims To Defend", package)

    def test_launch_note_states_narrow_claim(self):
        note = (ROOT / "docs" / "launch_note.md").read_text(encoding="utf-8")
        self.assertIn("visible handle != role-bound executable state", note)
        self.assertIn("active target -> semantic role -> executable handle", note)
        self.assertIn("StateBind Guard does not claim", note)


if __name__ == "__main__":
    unittest.main()
