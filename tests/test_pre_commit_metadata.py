import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PreCommitMetadataTests(unittest.TestCase):
    def test_hook_manifest_uses_installed_cli_quietly(self):
        text = (ROOT / ".pre-commit-hooks.yaml").read_text(encoding="utf-8")
        self.assertIn("id: statebind-guard", text)
        self.assertIn("entry: statebind validate statebind.json --repo . --fail-on warning --quiet", text)
        self.assertIn("language: python", text)
        self.assertIn("always_run: true", text)
        self.assertIn("pass_filenames: false", text)

    def test_docs_show_standard_pre_commit_config(self):
        text = (ROOT / "docs" / "pre_commit_usage.md").read_text(encoding="utf-8")
        config = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
        self.assertIn("https://github.com/FU-max-boop/statebind-guard", text)
        self.assertIn("rev: v0.1.29", text)
        self.assertIn("rev: v0.1.29", config)
        self.assertIn("id: statebind-guard", text)
        self.assertIn("pre-commit run statebind-guard --all-files", text)
        self.assertIn("statebind doctor --repo .", text)


if __name__ == "__main__":
    unittest.main()
