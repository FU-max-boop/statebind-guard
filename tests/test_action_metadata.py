import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GitHubActionMetadataTests(unittest.TestCase):
    def test_composite_action_exposes_ci_reports(self):
        text = (ROOT / "action.yml").read_text(encoding="utf-8")
        self.assertIn("using: composite", text)
        self.assertIn("statebind-json:", text)
        self.assertIn("fail-on:", text)
        self.assertIn("report:", text)
        self.assertIn("sarif:", text)
        self.assertIn("statebind_handoff/statebind_handoff.py", text)
        self.assertIn("--report \"$REPORT\"", text)
        self.assertIn("--sarif \"$SARIF\"", text)

    def test_repository_ci_smokes_local_action(self):
        text = (ROOT / ".github" / "workflows" / "smoke.yml").read_text(encoding="utf-8")
        self.assertIn("action-smoke:", text)
        self.assertIn("uses: ./", text)
        self.assertIn("test -s statebind-validation.json", text)
        self.assertIn("test -s statebind-validation.sarif", text)

    def test_repository_dogfoods_statebind_workflow(self):
        text = (ROOT / ".github" / "workflows" / "statebind-guard.yml").read_text(encoding="utf-8")
        self.assertIn("uses: ./", text)
        self.assertIn("handoff: HANDOFF.md", text)
        self.assertIn("statebind-json: statebind.json", text)
        self.assertIn("statebind-validation.sarif", text)


if __name__ == "__main__":
    unittest.main()
