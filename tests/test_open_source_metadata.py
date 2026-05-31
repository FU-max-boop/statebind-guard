import unittest
import os
import subprocess
import tempfile
from pathlib import Path

from statebind_handoff import __version__


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "statebind_handoff" / "statebind_handoff.py"
SKILL_SCRIPT = ROOT / "integrations" / "codex-skill" / "statebind-handoff" / "scripts" / "statebind_handoff.py"


class OpenSourceMetadataTests(unittest.TestCase):
    def test_citation_metadata_is_present(self):
        text = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
        self.assertIn("cff-version: 1.2.0", text)
        self.assertIn('title: "StateBind Guard"', text)
        self.assertIn('version: "0.1.32"', text)
        self.assertIn("repository-code: \"https://github.com/FU-max-boop/statebind-guard\"", text)
        self.assertIn("license: MIT", text)

    def test_version_surfaces_are_consistent(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        version_line = next(line for line in pyproject.splitlines() if line.startswith("version = "))
        version = version_line.split('"')[1]
        self.assertEqual(__version__, version)
        self.assertIn('license = "MIT"', pyproject)
        self.assertIn('requires = ["setuptools>=77"]', pyproject)
        self.assertNotIn("license = {", pyproject)
        self.assertNotIn("License :: OSI Approved", pyproject)
        self.assertIn(f'version: "{version}"', (ROOT / "CITATION.cff").read_text(encoding="utf-8"))
        self.assertIn(f"rev: v{version}", (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))

        out = subprocess.check_output(["python", str(SCRIPT), "--version"], cwd=ROOT, text=True)
        self.assertIn(version, out)

    def test_package_check_builds_clean_wheel_install(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("pip wheel --no-deps --no-build-isolation", makefile)
        self.assertIn("python -m venv \"$$tmpdir/venv\"", makefile)
        self.assertIn("PIP_FIND_LINKS=\"$$tmpdir/dist\"", makefile)
        self.assertIn("pip install statebind-guard", makefile)
        self.assertIn("statebind\" --version", makefile)

    def test_dist_check_builds_release_artifacts(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        build_script = (ROOT / "scripts" / "build_dist.py").read_text(encoding="utf-8")
        manifest = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")

        self.assertIn("dist-check:", makefile)
        self.assertIn("scripts/build_dist.py", makefile)
        self.assertIn("build_wheel", build_script)
        self.assertIn("build_sdist", build_script)
        self.assertIn("PIP_FIND_LINKS=\"$$tmpdir/dist\"", makefile)
        self.assertIn("statebind\" proof", makefile)
        self.assertIn("statebind\" doctor", makefile)
        self.assertIn("recursive-include schemas *.json", manifest)
        self.assertIn("recursive-include docs", manifest)

    def test_codex_skill_script_is_current_and_installable(self):
        self.assertEqual(SKILL_SCRIPT.read_text(encoding="utf-8"), SCRIPT.read_text(encoding="utf-8"))

        with tempfile.TemporaryDirectory() as codex_home, tempfile.TemporaryDirectory() as repo_dir:
            env = os.environ.copy()
            env["CODEX_HOME"] = codex_home
            subprocess.check_call(["bash", "scripts/install_codex_skill.sh"], cwd=ROOT, env=env)
            installed = Path(codex_home) / "skills" / "statebind-handoff" / "scripts" / "statebind_handoff.py"
            self.assertTrue(installed.exists())

            help_out = subprocess.check_output(["python", str(installed), "--help"], cwd=repo_dir, text=True)
            for command in ("init", "audit", "scout", "install-hook", "doctor", "policy", "proof", "validate"):
                self.assertIn(command, help_out)

            version_line = next(
                line for line in (ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines()
                if line.startswith("version = ")
            )
            version = version_line.split('"')[1]
            version_out = subprocess.check_output(["python", str(installed), "--version"], cwd=repo_dir, text=True)
            self.assertIn(version, version_out)

            subprocess.check_call(["python", str(installed), "proof"], cwd=repo_dir)
            subprocess.check_call(
                [
                    "python",
                    str(installed),
                    "init",
                    "--goal",
                    "skill install smoke",
                    "--next-command",
                    "make test",
                ],
                cwd=repo_dir,
            )
            subprocess.check_call(["python", str(installed), "policy", "--out", ".statebind-policy.json"], cwd=repo_dir)
            subprocess.check_call(
                ["python", str(installed), "validate", "statebind.json", "--repo", ".", "--fail-on", "warning"],
                cwd=repo_dir,
            )
            subprocess.check_call(
                ["python", str(installed), "doctor", "--repo", ".", "--policy", ".statebind-policy.json"],
                cwd=repo_dir,
            )

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
