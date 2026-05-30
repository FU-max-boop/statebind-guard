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

    def test_proof_runs_bad_vs_good_case(self):
        out = run(["python", str(SCRIPT), "proof"], ROOT)
        self.assertIn("StateBind proof", out)
        self.assertIn("bad_visible_unbound: FAIL", out)
        self.assertIn("good_role_bound: PASS", out)
        self.assertIn("vague_handle", out)

        proof_json = run(["python", str(SCRIPT), "proof", "--json"], ROOT)
        data = json.loads(proof_json)
        self.assertFalse(data["cases"]["bad_visible_unbound"]["passed"])
        self.assertTrue(data["cases"]["good_role_bound"]["passed"])
        self.assertTrue(
            any(
                finding["code"] == "vague_handle"
                for finding in data["cases"]["bad_visible_unbound"]["findings"]
            )
        )

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
            self.assertEqual(data["schema_version"], "0.1")
            self.assertIn("pytest tests/test_api.py::test_stream", text)
            self.assertNotIn("before handoff", text)
            self.assertEqual(data["raw_signals"]["repo"], ".")
            self.assertNotIn(str(repo), state.read_text())
            self.assertFalse(
                any(
                    b["role"] == "candidate_path" and "::" in b["handle"]
                    for b in data["bindings"]
                )
            )

    def test_validate_generated_contract_allows_draft_warnings(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "src").mkdir()
            (repo / "tests").mkdir()
            (repo / "src" / "api.py").write_text("x = 1\n")
            (repo / "tests" / "test_api.py").write_text("def test_stream(): pass\n")
            transcript = repo / "transcript.md"
            transcript.write_text("Run pytest tests/test_api.py::test_stream before continuing.\n")
            run(["git", "init", "-q"], repo)
            run(["git", "config", "user.email", "demo@example.com"], repo)
            run(["git", "config", "user.name", "Demo"], repo)
            run(["git", "add", "."], repo)
            run(["git", "commit", "-q", "-m", "init"], repo)

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
                    "--json",
                    str(state),
                    "--out",
                    str(repo / "HANDOFF.md"),
                ],
                repo,
            )

            text_out = run(["python", str(SCRIPT), "validate", str(state), "--repo", ".", "--fail-on", "error"], repo)
            self.assertIn("blank_task_goal", text_out)

            report = repo / "statebind-validation.json"
            run(
                [
                    "python",
                    str(SCRIPT),
                    "validate",
                    str(state),
                    "--repo",
                    ".",
                    "--fail-on",
                    "error",
                    "--report",
                    str(report),
                ],
                repo,
            )
            report_data = json.loads(report.read_text())
            self.assertTrue(report_data["passed"])
            self.assertEqual(report_data["schema_version"], "0.1")
            self.assertGreaterEqual(report_data["summary"]["warnings"], 1)

            sarif = repo / "statebind-validation.sarif"
            summary = repo / "statebind-summary.md"
            html_report = repo / "statebind-report.html"
            github_output = repo / "github-output.txt"
            proc = subprocess.run(
                [
                    "python",
                    str(SCRIPT),
                    "validate",
                    str(state),
                    "--repo",
                    ".",
                    "--fail-on",
                    "error",
                    "--sarif",
                    str(sarif),
                    "--summary",
                    str(summary),
                    "--html-report",
                    str(html_report),
                    "--json",
                    "--github-output",
                    str(github_output),
                    "--github-annotations",
                ],
                cwd=repo,
                text=True,
                capture_output=True,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertIn('"passed": true', proc.stdout)
            self.assertIn("::warning file=", proc.stderr)
            self.assertIn("StateBind blank_task_goal", proc.stderr)
            output_data = dict(line.split("=", 1) for line in github_output.read_text().splitlines())
            self.assertEqual(output_data["passed"], "true")
            self.assertEqual(output_data["errors"], "0")
            self.assertGreaterEqual(int(output_data["warnings"]), 1)
            self.assertEqual(output_data["exit_code"], "0")
            self.assertEqual(output_data["fail_on"], "error")
            self.assertEqual(output_data["statebind_json"], "statebind.json")
            sarif_data = json.loads(sarif.read_text())
            self.assertEqual(sarif_data["version"], "2.1.0")
            results = sarif_data["runs"][0]["results"]
            self.assertTrue(any(result["ruleId"] == "blank_task_goal" for result in results))
            self.assertTrue(all(result["level"] == "warning" for result in results))
            summary_text = summary.read_text()
            self.assertIn("# StateBind Guard", summary_text)
            self.assertIn("blank_task_goal", summary_text)
            self.assertIn("**Status:** PASS", summary_text)
            html_text = html_report.read_text()
            self.assertIn("<title>StateBind Guard Report</title>", html_text)
            self.assertIn("blank_task_goal", html_text)
            self.assertNotIn(str(repo), html_text)

            with self.assertRaises(subprocess.CalledProcessError):
                run(["python", str(SCRIPT), "validate", str(state), "--repo", ".", "--fail-on", "warning"], repo)

    def test_validate_applies_policy_as_code(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            run(
                [
                    "python",
                    str(SCRIPT),
                    "init",
                    "--goal",
                    "keep handoffs executable",
                    "--next-command",
                    "make test",
                ],
                repo,
            )
            policy = repo / ".statebind-policy.json"
            run(["python", str(SCRIPT), "policy", "--out", str(policy)], repo)
            policy_data = json.loads(policy.read_text())
            self.assertEqual(policy_data["preset"], "minimal")
            self.assertEqual(policy_data["required_roles"], ["next_command"])

            ok_report = repo / "policy-ok.json"
            ok_summary = repo / "policy-ok.md"
            ok_html = repo / "policy-ok.html"
            run(
                [
                    "python",
                    str(SCRIPT),
                    "validate",
                    "statebind.json",
                    "--repo",
                    ".",
                    "--policy",
                    str(policy),
                    "--report",
                    str(ok_report),
                    "--summary",
                    str(ok_summary),
                    "--html-report",
                    str(ok_html),
                    "--fail-on",
                    "warning",
                ],
                repo,
            )
            ok_data = json.loads(ok_report.read_text())
            self.assertTrue(ok_data["passed"])
            self.assertEqual(ok_data["policy"], str(policy))
            self.assertIn("**Policy:**", ok_summary.read_text())
            self.assertIn(".statebind-policy.json", ok_html.read_text())

            strict_policy = repo / "strict-policy.json"
            strict_policy.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "required_roles": ["release_gate_command"],
                        "min_confidence": "high",
                        "require_top_level_risks": True,
                    }
                )
            )
            fail_summary = repo / "policy-fail.md"
            proc = subprocess.run(
                [
                    "python",
                    str(SCRIPT),
                    "validate",
                    "statebind.json",
                    "--repo",
                    ".",
                    "--policy",
                    str(strict_policy),
                    "--summary",
                    str(fail_summary),
                    "--fail-on",
                    "error",
                ],
                cwd=repo,
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("policy_missing_required_role", proc.stdout)
            self.assertIn("policy_missing_top_level_risks", proc.stdout)
            self.assertIn("**Status:** FAIL", fail_summary.read_text())

    def test_policy_presets_generate_scenario_gates(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            presets_out = run(["python", str(SCRIPT), "policy", "--list-presets"], repo)
            self.assertIn("bugfix", presets_out)
            self.assertIn("release", presets_out)
            self.assertIn("benchmark", presets_out)

            release_policy = repo / "release-policy.json"
            run(
                [
                    "python",
                    str(SCRIPT),
                    "policy",
                    "--preset",
                    "release",
                    "--out",
                    str(release_policy),
                ],
                repo,
            )
            data = json.loads(release_policy.read_text())
            self.assertEqual(data["preset"], "release")
            self.assertEqual(data["min_confidence"], "high")
            self.assertTrue(data["require_top_level_risks"])
            self.assertIn("release_gate_command", data["required_roles"])
            self.assertIn("artifact_path", data["required_roles"])

            run(
                [
                    "python",
                    str(SCRIPT),
                    "init",
                    "--goal",
                    "release package",
                    "--next-command",
                    "make public-check",
                ],
                repo,
            )
            proc = subprocess.run(
                [
                    "python",
                    str(SCRIPT),
                    "validate",
                    "statebind.json",
                    "--repo",
                    ".",
                    "--policy",
                    str(release_policy),
                    "--fail-on",
                    "error",
                ],
                cwd=repo,
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("policy_missing_required_role", proc.stdout)
            self.assertIn("release_gate_command", proc.stdout)

    def test_init_writes_ready_scaffold(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            handoff = repo / "HANDOFF.md"
            state = repo / "statebind.json"
            workflow = repo / ".github" / "workflows" / "statebind-guard.yml"

            out = run(
                [
                    "python",
                    str(SCRIPT),
                    "init",
                    "--goal",
                    "keep agent handoffs executable",
                    "--next-command",
                    "python -m unittest discover -s tests",
                ],
                repo,
            )

            self.assertIn("Wrote", out)
            self.assertTrue(handoff.exists())
            self.assertTrue(state.exists())
            self.assertTrue(workflow.exists())
            workflow_text = workflow.read_text()
            self.assertIn("FU-max-boop/statebind-guard@v0.1.15", workflow_text)
            self.assertIn("handoff: HANDOFF.md", workflow_text)
            self.assertIn("statebind-json: statebind.json", workflow_text)

            data = json.loads(state.read_text())
            self.assertEqual(data["task"]["goal"], "keep agent handoffs executable")
            self.assertEqual(data["bindings"][0]["handle"], "python -m unittest discover -s tests")

            check_out = run(["python", str(SCRIPT), "check", str(handoff)], repo)
            self.assertIn("Basic handoff check passed", check_out)

            validate_out = run(
                [
                    "python",
                    str(SCRIPT),
                    "validate",
                    str(state),
                    "--repo",
                    ".",
                    "--fail-on",
                    "warning",
                ],
                repo,
            )
            self.assertIn("StateBind validation passed", validate_out)

            doctor_out = run(["python", str(SCRIPT), "doctor", "--repo", "."], repo)
            self.assertIn("StateBind adoption doctor", doctor_out)
            self.assertIn("[ok] statebind_json", doctor_out)
            self.assertIn("[ok] statebind_validation", doctor_out)
            self.assertIn("[warning] local_git_hook", doctor_out)

            doctor_json = run(["python", str(SCRIPT), "doctor", "--repo", ".", "--json"], repo)
            doctor_data = json.loads(doctor_json)
            self.assertTrue(doctor_data["passed"])
            self.assertEqual(doctor_data["summary"]["errors"], 0)
            self.assertGreaterEqual(doctor_data["summary"]["warnings"], 1)

            quiet_proc = subprocess.run(
                [
                    "python",
                    str(SCRIPT),
                    "validate",
                    str(state),
                    "--repo",
                    ".",
                    "--fail-on",
                    "warning",
                    "--quiet",
                ],
                cwd=repo,
                text=True,
                capture_output=True,
            )
            self.assertEqual(quiet_proc.returncode, 0)
            self.assertEqual(quiet_proc.stdout, "")

    def test_init_refuses_to_partially_overwrite_existing_files(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            handoff = repo / "HANDOFF.md"
            state = repo / "statebind.json"
            workflow = repo / ".github" / "workflows" / "statebind-guard.yml"
            handoff.write_text("existing handoff\n")

            proc = subprocess.run(
                [
                    "python",
                    str(SCRIPT),
                    "init",
                    "--handoff",
                    str(handoff),
                    "--json",
                    str(state),
                    "--workflow",
                    str(workflow),
                ],
                cwd=repo,
                text=True,
                capture_output=True,
            )

            self.assertEqual(proc.returncode, 2)
            self.assertIn("pass --force", proc.stderr)
            self.assertEqual(handoff.read_text(), "existing handoff\n")
            self.assertFalse(state.exists())
            self.assertFalse(workflow.exists())

    def test_install_hook_validates_statebind_before_commit(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            run(["git", "init", "-q"], repo)
            run(["git", "config", "user.email", "demo@example.com"], repo)
            run(["git", "config", "user.name", "Demo"], repo)

            run(
                [
                    "python",
                    str(SCRIPT),
                    "init",
                    "--goal",
                    "keep handoffs executable",
                    "--next-command",
                    "make test",
                ],
                repo,
            )
            policy = repo / ".statebind-policy.json"
            run(["python", str(SCRIPT), "policy", "--out", str(policy)], repo)
            out = run(
                [
                    "python",
                    str(SCRIPT),
                    "install-hook",
                    "--repo",
                    ".",
                    "--json",
                    "statebind.json",
                    "--policy",
                    str(policy),
                ],
                repo,
            )
            hook = repo / ".git" / "hooks" / "pre-commit"
            self.assertIn("pre-commit", out)
            self.assertIn("will apply policy", out)
            self.assertTrue(hook.exists())
            self.assertTrue(hook.stat().st_mode & 0o111)
            hook_text = hook.read_text()
            self.assertIn("statebind_handoff.statebind_handoff", hook_text)
            self.assertIn("--fail-on warning", hook_text)
            self.assertIn("--quiet", hook_text)
            self.assertIn("STATEBIND_POLICY", hook_text)
            self.assertIn("--policy", hook_text)

            doctor_out = run(["python", str(SCRIPT), "doctor", "--repo", "."], repo)
            self.assertIn("[ok] local_git_hook", doctor_out)

            (repo / "README.md").write_text("demo\n")
            run(["git", "add", "."], repo)
            run(["git", "commit", "-q", "-m", "valid handoff"], repo)

            data = json.loads((repo / "statebind.json").read_text())
            data["bindings"][0]["handle"] = "the previous command"
            (repo / "statebind.json").write_text(json.dumps(data, indent=2))
            (repo / "README.md").write_text("demo change\n")
            run(["git", "add", "."], repo)
            proc = subprocess.run(
                ["git", "commit", "-m", "invalid handoff"],
                cwd=repo,
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("vague_handle", proc.stdout + proc.stderr)

    def test_install_hook_refuses_existing_hook_without_force(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            run(["git", "init", "-q"], repo)
            hook = repo / ".git" / "hooks" / "pre-commit"
            hook.write_text("#!/usr/bin/env sh\nexit 0\n")

            proc = subprocess.run(
                ["python", str(SCRIPT), "install-hook", "--repo", "."],
                cwd=repo,
                text=True,
                capture_output=True,
            )

            self.assertEqual(proc.returncode, 2)
            self.assertIn("pass --force", proc.stderr)
            self.assertEqual(hook.read_text(), "#!/usr/bin/env sh\nexit 0\n")

    def test_validate_rejects_vague_handle(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            state = repo / "statebind.json"
            state.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "task": {"goal": "resume work", "status": "ready"},
                        "active_target": {
                            "type": "test",
                            "handle": "the test above",
                            "evidence": "summary",
                            "confidence": "high",
                        },
                        "bindings": [
                            {
                                "role": "failing_test",
                                "handle": "the previous command",
                                "evidence": "summary",
                                "confidence": "high",
                                "risk": "",
                            }
                        ],
                        "risks": [],
                    }
                )
            )
            sarif = repo / "statebind-validation.sarif"
            proc = subprocess.run(
                [
                    "python",
                    str(SCRIPT),
                    "doctor",
                    "--repo",
                    ".",
                    "--statebind-json",
                    str(state),
                ],
                cwd=repo,
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("vague_handle", proc.stdout)

            proc = subprocess.run(
                [
                    "python",
                    str(SCRIPT),
                    "validate",
                    str(state),
                    "--repo",
                    ".",
                    "--fail-on",
                    "error",
                    "--sarif",
                    str(sarif),
                ],
                cwd=repo,
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(proc.returncode, 0)
            sarif_data = json.loads(sarif.read_text())
            results = sarif_data["runs"][0]["results"]
            self.assertTrue(any(result["ruleId"] == "vague_handle" for result in results))
            self.assertTrue(any(result["level"] == "error" for result in results))

    def test_validate_missing_contract_exits_cleanly(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            sarif = repo / "missing-statebind.sarif"
            summary = repo / "missing-statebind.md"
            html_report = repo / "missing-statebind.html"
            github_output = repo / "missing-github-output.txt"
            proc = subprocess.run(
                [
                    "python",
                    str(SCRIPT),
                    "validate",
                    "missing-statebind.json",
                    "--repo",
                    ".",
                    "--sarif",
                    str(sarif),
                    "--summary",
                    str(summary),
                    "--html-report",
                    str(html_report),
                    "--github-output",
                    str(github_output),
                    "--github-annotations",
                ],
                cwd=repo,
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("StateBind contract not found", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)
            sarif_data = json.loads(sarif.read_text())
            self.assertEqual(sarif_data["runs"][0]["results"][0]["ruleId"], "contract_not_found")
            self.assertIn("contract_not_found", summary.read_text())
            self.assertIn("contract_not_found", html_report.read_text())

            self.assertIn("::error file=missing-statebind.json", proc.stderr)
            output_data = dict(line.split("=", 1) for line in github_output.read_text().splitlines())
            self.assertEqual(output_data["passed"], "false")
            self.assertEqual(output_data["errors"], "1")
            self.assertEqual(output_data["warnings"], "0")
            self.assertEqual(output_data["exit_code"], "1")

    def test_schema_command_matches_tracked_schema(self):
        out = run(["python", str(SCRIPT), "schema"], ROOT)
        generated = json.loads(out)
        tracked = json.loads((ROOT / "schemas" / "statebind.schema.json").read_text())
        self.assertEqual(generated, tracked)
        self.assertEqual(tracked["properties"]["schema_version"]["enum"], ["0.1"])

        policy_out = run(["python", str(SCRIPT), "schema", "--policy"], ROOT)
        generated_policy = json.loads(policy_out)
        tracked_policy = json.loads((ROOT / "schemas" / "statebind-policy.schema.json").read_text())
        self.assertEqual(generated_policy, tracked_policy)
        self.assertEqual(tracked_policy["properties"]["schema_version"]["enum"], ["0.1"])


if __name__ == "__main__":
    unittest.main()
