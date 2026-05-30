import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OpenSourceMetadataTests(unittest.TestCase):
    def test_citation_metadata_is_present(self):
        text = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
        self.assertIn("cff-version: 1.2.0", text)
        self.assertIn('title: "StateBind Guard"', text)
        self.assertIn('version: "0.1.15"', text)
        self.assertIn("repository-code: \"https://github.com/FU-max-boop/statebind-guard\"", text)
        self.assertIn("license: MIT", text)

    def test_issue_templates_cover_adoption_and_failures(self):
        template_dir = ROOT / ".github" / "ISSUE_TEMPLATE"
        adoption = (template_dir / "adoption_report.yml").read_text(encoding="utf-8")
        failure = (template_dir / "failure_case.yml").read_text(encoding="utf-8")
        bug = (template_dir / "bug_report.yml").read_text(encoding="utf-8")
        config = (template_dir / "config.yml").read_text(encoding="utf-8")

        self.assertIn("Adoption report", adoption)
        self.assertIn("Adoption friction", adoption)
        self.assertIn("Failure case", failure)
        self.assertIn("wrong test", failure)
        self.assertIn("Bug report", bug)
        self.assertIn("Launch package", config)

    def test_pr_template_and_feedback_docs_exist(self):
        pr = (ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")
        feedback = (ROOT / "docs" / "adoption_feedback.md").read_text(encoding="utf-8")
        self.assertIn("StateBind impact", pr)
        self.assertIn("Roadmap", roadmap)
        self.assertIn("Adoption And Feedback", feedback)
        self.assertIn("wrong-object", roadmap)
        self.assertIn("Good Feedback Shape", feedback)


if __name__ == "__main__":
    unittest.main()
