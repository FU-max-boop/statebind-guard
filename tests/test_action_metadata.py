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
        self.assertIn("summary:", text)
        self.assertIn("html-report:", text)
        self.assertIn("policy:", text)
        self.assertIn("annotations:", text)
        self.assertIn("passed:", text)
        self.assertIn("errors:", text)
        self.assertIn("warnings:", text)
        self.assertIn("exit_code:", text)
        self.assertIn("fail_on:", text)
        self.assertIn("statebind_json:", text)
        self.assertIn("id: validate", text)
        self.assertIn("statebind_handoff/statebind_handoff.py", text)
        self.assertIn("--report \"$REPORT\"", text)
        self.assertIn("--sarif \"$SARIF\"", text)
        self.assertIn("--summary \"$SUMMARY\"", text)
        self.assertIn("--html-report \"$HTML_REPORT\"", text)
        self.assertIn("POLICY_ARGS", text)
        self.assertIn("OUTPUT_ARGS", text)
        self.assertIn("--github-output \"$GITHUB_OUTPUT\"", text)
        self.assertIn("ANNOTATION_ARGS", text)
        self.assertIn("--github-annotations", text)
        self.assertIn("GITHUB_STEP_SUMMARY", text)

    def test_repository_ci_smokes_local_action(self):
        text = (ROOT / ".github" / "workflows" / "smoke.yml").read_text(encoding="utf-8")
        self.assertIn("action-smoke:", text)
        self.assertIn("uses: ./", text)
        self.assertIn("id: statebind", text)
        self.assertIn("STATEBIND_PASSED", text)
        self.assertIn("steps.statebind.outputs.passed", text)
        self.assertIn("steps.statebind.outputs.exit_code", text)
        self.assertIn("test -s statebind-validation.json", text)
        self.assertIn("test -s statebind-validation.sarif", text)
        self.assertIn("test -s statebind-summary.md", text)
        self.assertIn("test -s statebind-report.html", text)
        self.assertIn("policy: .statebind-policy.json", text)
        self.assertIn("id: statebind_invalid", text)
        self.assertIn("continue-on-error: true", text)
        self.assertIn("steps.statebind_invalid.outcome", text)
        self.assertIn("STATEBIND_INVALID_PASSED", text)
        self.assertIn("STATEBIND_INVALID_ERRORS", text)
        self.assertIn("STATEBIND_INVALID_EXIT_CODE", text)
        self.assertIn("statebind-invalid-validation.json", text)
        self.assertIn("statebind-invalid-validation.sarif", text)
        self.assertIn("statebind-invalid-summary.md", text)
        self.assertIn("statebind-invalid-report.html", text)
        self.assertIn("vague_handle", text)

    def test_repository_dogfoods_statebind_workflow(self):
        text = (ROOT / ".github" / "workflows" / "statebind-guard.yml").read_text(encoding="utf-8")
        self.assertIn("uses: ./", text)
        self.assertIn("handoff: HANDOFF.md", text)
        self.assertIn("statebind-json: statebind.json", text)
        self.assertIn("policy: .statebind-policy.json", text)
        self.assertIn("statebind-validation.sarif", text)
        self.assertIn("statebind-summary.md", text)
        self.assertIn("statebind-report.html", text)


if __name__ == "__main__":
    unittest.main()
