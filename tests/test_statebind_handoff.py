import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "statebind_handoff" / "statebind_handoff.py"


def run(cmd, cwd):
    return subprocess.check_output(cmd, cwd=cwd, text=True)


class StateBindHandoffTests(unittest.TestCase):
    def test_demo_runs(self):
        out = run(["python", str(SCRIPT), "demo"], ROOT)
        self.assertIn("Visible ID But Unbound", out)
        self.assertIn("comparison_base_sha", out)

    def test_extract_redacts_with_labels(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "src").mkdir()
            (repo / "tests").mkdir()
            (repo / "src" / "api.py").write_text("x = 1\n")
            (repo / "tests" / "test_api.py").write_text("def test_stream(): pass\n")
            transcript = repo / "transcript.md"
            transcript.write_text(
                "Run pytest tests/test_api.py::test_stream before handoff. "
                "Base sha def5678, head sha abc1234.\n"
            )
            run(["git", "init", "-q"], repo)
            run(["git", "config", "user.email", "demo@example.com"], repo)
            run(["git", "config", "user.name", "Demo"], repo)
            run(["git", "add", "."], repo)
            run(["git", "commit", "-q", "-m", "init"], repo)
            (repo / "src" / "api.py").write_text("x = 2\n")

            handoff = repo / "HANDOFF.md"
            state = repo / "statebind.json"
            run(
                [
                    "python",
                    str(SCRIPT),
                    "extract",
                    "--repo",
                    ".",
                    "--transcript",
                    "transcript.md",
                    "--repo-label",
                    ".",
                    "--transcript-label",
                    "transcript.md",
                    "--out",
                    str(handoff),
                    "--json",
                    str(state),
                ],
                repo,
            )
            text = handoff.read_text()
            data = json.loads(state.read_text())
            self.assertIn("pytest tests/test_api.py::test_stream", text)
            self.assertNotIn("before handoff", text)
            self.assertEqual(data["raw_signals"]["repo"], ".")
            self.assertNotIn(str(repo), state.read_text())


if __name__ == "__main__":
    unittest.main()
