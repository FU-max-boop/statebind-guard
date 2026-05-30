import unittest
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DocsSiteTests(unittest.TestCase):
    def test_landing_page_links_product_surface(self):
        html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
        self.assertIn("StateBind Guard v0.1.23", html)
        self.assertIn("Make coding-agent handoffs executable.", html)
        self.assertIn("assets/statebind_guard_demo.svg", html)
        self.assertIn("assets/statebind_social_preview.png", html)
        self.assertIn('property="og:image"', html)
        self.assertIn('name="twitter:card" content="summary_large_image"', html)
        self.assertIn("FU-max-boop/statebind-guard@v0.1.23", html)
        self.assertIn("statebind proof", html)
        self.assertIn("statebind audit --repo .", html)
        self.assertIn("statebind init", html)
        self.assertIn("statebind install-hook", html)
        self.assertIn("statebind doctor", html)
        self.assertIn("Policy-as-code", html)
        self.assertIn("Adoption audit", html)
        self.assertIn("Launch package", html)
        self.assertIn("Launch-ready package", html)
        self.assertIn("Feedback-ready", html)
        self.assertIn("Markdown summaries", html)
        self.assertIn("HTML reports", html)
        self.assertIn("GitHub annotations", html)
        self.assertIn("action outputs", html)
        self.assertIn("https://github.com/FU-max-boop/statebind-guard/releases/tag/v0.1.23", html)
        self.assertIn("docs/launch_note.md", html)
        self.assertIn("docs/launch_package.md", html)
        self.assertIn("docs/adoption_audit.md", html)
        self.assertIn("docs/roadmap.md", html)
        self.assertIn("issues/new/choose", html)
        self.assertIn("docs/pre_commit_usage.md", html)
        self.assertIn("docs/policy_usage.md", html)
        self.assertIn("docs/adoption_examples.md", html)
        self.assertIn("External adoption receipt", html)
        self.assertIn("statebind-guard-adoption-example", html)
        self.assertIn("26683277633", html)

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
        self.assertIn("docs/roadmap.md", readme)
        self.assertIn("docs/adoption_feedback.md", readme)
        self.assertIn("docs/adoption_audit.md", readme)
        self.assertIn("CITATION.cff", readme)
        self.assertIn("docs/pre_commit_usage.md", readme)
        self.assertIn("docs/policy_usage.md", readme)
        self.assertIn("docs/adoption_examples.md", readme)
        self.assertIn("docs/result_cards/statebind_guard_deployed_corpus.md", readme)
        self.assertIn("statebind-guard-adoption-example", readme)
        self.assertIn("actions/runs/26683277633", readme)
        self.assertIn("statebind install-hook", readme)
        self.assertIn("statebind doctor", readme)
        self.assertIn("statebind policy", readme)
        self.assertIn("statebind policy --preset bugfix", readme)
        self.assertIn("bug fixes, CI failures, releases, migrations, and benchmark runs", readme)
        self.assertIn("statebind proof", readme)
        self.assertIn("statebind audit --repo .", readme)
        self.assertIn("bad_visible_unbound: FAIL", readme)
        self.assertIn("good_role_bound: PASS", readme)
        self.assertIn("actions/workflows/smoke.yml/badge.svg", readme)

    def test_launch_package_contains_outreach_material(self):
        package = (ROOT / "docs" / "launch_package.md").read_text(encoding="utf-8")
        self.assertIn("One-Liner", package)
        self.assertIn("Maintainer Pitch", package)
        self.assertIn("Launch Post", package)
        self.assertIn("statebind proof", package)
        self.assertIn("statebind audit --repo .", package)
        self.assertIn("bad_visible_unbound: FAIL", package)
        self.assertIn("good_role_bound: PASS", package)
        self.assertIn("Technical Claims To Defend", package)
        self.assertIn("Feedback Loop", package)
        self.assertIn("adoption_feedback.md", package)
        self.assertIn("roadmap.md", package)
        self.assertIn("statebind-guard-adoption-example", package)
        self.assertIn("26683277633", package)
        self.assertIn("deployed-derived", package)

    def test_external_adoption_receipt_is_linked(self):
        receipt = (ROOT / "docs" / "adoption_examples.md").read_text(encoding="utf-8")
        industrial = (ROOT / "docs" / "industrial_adoption.md").read_text(encoding="utf-8")
        action_usage = (ROOT / "docs" / "github_action_usage.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

        for text in (receipt, industrial, action_usage):
            self.assertIn("statebind-guard-adoption-example", text)
            self.assertIn("FU-max-boop/statebind-guard@v0.1.13", text)
            self.assertIn("26683277633", text)
            self.assertIn("passed=true", text)
            self.assertIn("warnings=0", text)

        self.assertIn("859c500", receipt)
        self.assertIn("adoption_examples.md", industrial)
        self.assertIn("FU-max-boop/statebind-guard@v0.1.23", industrial)
        self.assertIn("FU-max-boop/statebind-guard@v0.1.23", action_usage)
        self.assertIn("current public adoption receipt", roadmap)

    def test_launch_note_states_narrow_claim(self):
        note = (ROOT / "docs" / "launch_note.md").read_text(encoding="utf-8")
        self.assertIn("visible handle != role-bound executable state", note)
        self.assertIn("active target -> semantic role -> executable handle", note)
        self.assertIn("statebind policy --preset bugfix", note)
        self.assertIn("StateBind Guard does not claim", note)

    def test_adoption_audit_doc_has_first_pr_flow(self):
        audit = (ROOT / "docs" / "adoption_audit.md").read_text(encoding="utf-8")
        self.assertIn("statebind audit --repo . --markdown", audit)
        self.assertIn("--issue-template", audit)
        self.assertIn("not_started", audit)
        self.assertIn("partial", audit)
        self.assertIn("wired", audit)
        self.assertIn("Smallest Adoption PR", audit)
        self.assertIn("Privacy Boundary", audit)

    def test_policy_usage_documents_presets(self):
        policy = (ROOT / "docs" / "policy_usage.md").read_text(encoding="utf-8")
        self.assertIn("statebind policy --list-presets", policy)
        self.assertIn("statebind policy --preset release", policy)
        self.assertIn("`bugfix`", policy)
        self.assertIn("`ci-failure`", policy)
        self.assertIn("`benchmark`", policy)


if __name__ == "__main__":
    unittest.main()
