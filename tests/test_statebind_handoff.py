import importlib.util
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "statebind_handoff" / "statebind_handoff.py"
SPEC = importlib.util.spec_from_file_location("statebind_handoff_script", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


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

    def test_version_flag_matches_package_metadata(self):
        out = run(["python", str(SCRIPT), "--version"], ROOT)
        version_line = next(
            line for line in (ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines()
            if line.startswith("version = ")
        )
        version = version_line.split('"')[1]
        self.assertIn(version, out)

    def test_validate_rejects_schema_required_field_omissions(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            state = repo / "statebind.json"
            state.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "task": {"goal": "resume work"},
                        "active_target": {
                            "type": "ci",
                            "handle": "make test",
                            "evidence": "summary",
                        },
                        "bindings": [
                            {
                                "role": "next_command",
                                "handle": "make test",
                                "evidence": "summary",
                                "confidence": "high",
                            }
                        ],
                        "risks": [],
                    }
                )
            )

            proc = subprocess.run(
                [
                    "python",
                    str(SCRIPT),
                    "validate",
                    str(state),
                    "--repo",
                    ".",
                    "--fail-on",
                    "warning",
                    "--json",
                ],
                cwd=repo,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(proc.returncode, 0)
            report = json.loads(proc.stdout)
            codes = {finding["code"] for finding in report["findings"]}
            self.assertIn("missing_task_status", codes)
            self.assertIn("missing_active_target_confidence", codes)
            self.assertIn("blank_active_target_confidence", codes)
            self.assertIn("missing_binding_risk", codes)
            self.assertGreaterEqual(report["summary"]["errors"], 4)

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
            self.assertIn("FU-max-boop/statebind-guard@v0.1.34", workflow_text)
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

    def test_audit_guides_pre_adoption_repo(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "AGENTS.md").write_text("# Agent notes\nUse handoffs for long coding tasks.\n")
            (repo / "Makefile").write_text("test:\n\tpython -m unittest discover -s tests\n")

            audit_md = repo / "statebind-audit.md"
            issue_template = repo / "statebind-issue.md"
            audit_json = run(
                [
                    "python",
                    str(SCRIPT),
                    "audit",
                    "--repo",
                    ".",
                    "--json",
                    "--markdown",
                    str(audit_md),
                    "--issue-template",
                    str(issue_template),
                ],
                repo,
            )
            data = json.loads(audit_json)

            self.assertEqual(data["adoption_level"], "partial")
            self.assertEqual(data["suggested_next_command"]["command"], "make test")
            self.assertTrue(any(candidate["path"] == "AGENTS.md" for candidate in data["handoff_candidates"]))
            self.assertTrue(any(check["code"] == "statebind_json" for check in data["checks"]))
            self.assertIn("statebind init", "\n".join(data["recommended_commands"]))

            audit_text = audit_md.read_text()
            self.assertIn("# StateBind Adoption Audit", audit_text)
            self.assertIn("Smallest Adoption PR", audit_text)
            self.assertIn('statebind init --goal "Preserve executable coding-agent handoffs" --next-command "make test"', audit_text)
            self.assertNotIn(str(repo), audit_text)

            issue_text = issue_template.read_text()
            self.assertIn("StateBind Guard pre-adoption audit", issue_text)
            self.assertIn("Repository", issue_text)
            self.assertIn("not a request to adopt a dependency blindly", issue_text)
            self.assertIn("Suggested smallest local gate", issue_text)
            self.assertIn("Smallest possible adoption PR", issue_text)
            self.assertIn("Maintainer questions", issue_text)
            self.assertIn("make test", issue_text)
            self.assertIn("Privacy boundary", issue_text)
            self.assertNotIn(str(repo), issue_text)

    def test_audit_clones_repo_url_without_leaking_temp_checkout(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "source-repo"
            source.mkdir()
            (source / "AGENTS.md").write_text("# Agent notes\nResume long-running coding tasks carefully.\n")
            (source / "Makefile").write_text("test:\n\tpython -m unittest discover -s tests\n")
            run(["git", "init", "-q"], source)
            run(["git", "config", "user.email", "demo@example.com"], source)
            run(["git", "config", "user.name", "Demo"], source)
            run(["git", "add", "."], source)
            run(["git", "commit", "-q", "-m", "init"], source)

            issue_template = root / "remote-issue.md"
            audit_json = run(
                [
                    "python",
                    str(SCRIPT),
                    "audit",
                    "--repo-url",
                    source.as_posix(),
                    "--json",
                    "--issue-template",
                    str(issue_template),
                ],
                ROOT,
            )
            data = json.loads(audit_json)

            self.assertEqual(data["repo"], "source-repo")
            self.assertEqual(data["adoption_level"], "partial")
            self.assertEqual(data["suggested_next_command"]["command"], "make test")
            self.assertTrue(any(candidate["path"] == "AGENTS.md" for candidate in data["handoff_candidates"]))

            issue_text = issue_template.read_text()
            self.assertIn("StateBind Guard pre-adoption audit", issue_text)
            self.assertIn("`source-repo`", issue_text)
            self.assertIn("Maintainer questions", issue_text)
            self.assertIn("AGENTS.md", issue_text)
            self.assertNotIn(str(root), issue_text)
            self.assertNotIn("statebind-audit-", issue_text)

    def test_audit_repo_url_reports_clone_failure(self):
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "missing-repo"
            proc = subprocess.run(
                [
                    "python",
                    str(SCRIPT),
                    "audit",
                    "--repo-url",
                    missing.as_posix(),
                    "--clone-timeout",
                    "1",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(proc.returncode, 2)
            self.assertEqual(proc.stdout, "")
            self.assertIn("StateBind audit failed:", proc.stderr)

    def test_audit_reports_wired_repo_after_init(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            run(["git", "init", "-q"], repo)
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
            run(["python", str(SCRIPT), "policy", "--out", ".statebind-policy.json"], repo)

            issue_template = repo / "wired-issue.md"
            audit_json = run(
                [
                    "python",
                    str(SCRIPT),
                    "audit",
                    "--repo",
                    ".",
                    "--json",
                    "--issue-template",
                    str(issue_template),
                ],
                repo,
            )
            data = json.loads(audit_json)
            self.assertEqual(data["adoption_level"], "wired")
            codes = {check["code"]: check["status"] for check in data["checks"]}
            self.assertEqual(codes["statebind_json"], "ok")
            self.assertEqual(codes["github_action"], "ok")
            self.assertEqual(codes["policy_file"], "ok")
            issue_text = issue_template.read_text()
            self.assertIn("Smallest follow-up check", issue_text)
            self.assertIn("already appears wired", issue_text)
            self.assertIn("statebind validate statebind.json", issue_text)

    def test_scout_ranks_repositories_and_writes_notes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            high = root / "handoff-heavy"
            low = root / "plain-repo"
            for repo in (high, low):
                repo.mkdir()
                run(["git", "init", "-q"], repo)
                run(["git", "config", "user.email", "demo@example.com"], repo)
                run(["git", "config", "user.name", "Demo"], repo)
            (high / "AGENTS.md").write_text("# Agent notes\nResume long coding tasks from explicit handoffs.\n")
            (high / "Makefile").write_text("test:\n\tpython -m unittest discover -s tests\n")
            (low / "README.md").write_text("# Plain repo\n")
            for repo in (high, low):
                run(["git", "add", "."], repo)
                run(["git", "commit", "-q", "-m", "init"], repo)

            markdown = root / "scout.md"
            result_card = root / "scout-card.md"
            issue_dir = root / "notes"
            scout_json = run(
                [
                    "python",
                    str(SCRIPT),
                    "scout",
                    "--repo-url",
                    high.as_posix(),
                    "--repo-url",
                    low.as_posix(),
                    "--json",
                    "--markdown",
                    str(markdown),
                    "--result-card",
                    str(result_card),
                    "--issue-dir",
                    str(issue_dir),
                ],
                ROOT,
            )
            data = json.loads(scout_json)

            self.assertEqual(data["summary"]["total"], 2)
            self.assertEqual(data["summary"]["ok"], 2)
            first = data["repositories"][0]
            second = data["repositories"][1]
            self.assertEqual(first["repo"], "handoff-heavy")
            self.assertEqual(first["priority"], "high")
            self.assertEqual(first["suggested_next_command"]["command"], "make test")
            self.assertEqual(second["repo"], "plain-repo")
            self.assertEqual(second["priority"], "skip")

            report = markdown.read_text()
            self.assertIn("# StateBind Adoption Scout", report)
            self.assertIn("handoff-heavy", report)
            self.assertIn("plain-repo", report)
            self.assertIn("Prefer `high` or `medium` targets", report)
            self.assertNotIn(str(root), report)

            card = result_card.read_text()
            self.assertIn("# StateBind Scout Result Card", card)
            self.assertIn("repositories scanned: 2", card)
            self.assertIn("| `high` | 1 |", card)
            self.assertIn("| `skip` | 1 |", card)
            self.assertIn("generated maintainer-note drafts: 1", card)
            self.assertIn("handoff-heavy", card)
            self.assertIn("triage artifact", card)

            notes = sorted(path.name for path in issue_dir.glob("*.md"))
            self.assertEqual(notes, ["handoff-heavy-statebind-note.md"])
            note_text = (issue_dir / notes[0]).read_text()
            self.assertIn("AGENTS.md", note_text)
            self.assertNotIn(str(root), note_text)

    def test_scout_requires_a_repository_source(self):
        proc = subprocess.run(
            ["python", str(SCRIPT), "scout", "--json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual(proc.returncode, 2)
        self.assertIn("needs at least one", proc.stderr)

    def test_github_api_scout_report_without_git_clone(self):
        original_snapshot = MODULE.github_snapshot

        def fake_snapshot(owner_repo, ref, timeout):
            self.assertEqual(owner_repo, "owner/agent-repo")
            self.assertIsNone(ref)
            self.assertEqual(timeout, 7)
            return (
                "agent-repo",
                [
                    "AGENTS.md",
                    "Makefile",
                    ".github/workflows/statebind-guard.yml",
                ],
                {
                    "Makefile": "test:\n\tpython -m unittest discover -s tests\n",
                    ".github/workflows/statebind-guard.yml": "uses: FU-max-boop/statebind-guard@v0.1.34\n",
                },
            )

        MODULE.github_snapshot = fake_snapshot
        try:
            report = MODULE.audit_github_report(
                "owner/agent-repo",
                None,
                7,
                Path("statebind.json"),
                Path("HANDOFF.md"),
                Path(".github/workflows/statebind-guard.yml"),
                None,
            )
        finally:
            MODULE.github_snapshot = original_snapshot

        self.assertEqual(report["repo"], "agent-repo")
        self.assertEqual(report["adoption_level"], "partial")
        self.assertEqual(report["suggested_next_command"]["command"], "make test")
        self.assertTrue(any(candidate["path"] == "AGENTS.md" for candidate in report["handoff_candidates"]))
        self.assertEqual(report["statebind_workflows"], [".github/workflows/statebind-guard.yml"])
        record = MODULE.scout_record_from_report("owner/agent-repo", report, None)
        self.assertEqual(record["priority"], "high")
        self.assertGreaterEqual(record["score"], 8)

    def test_github_api_scout_writes_issue_context_card(self):
        original_snapshot = MODULE.github_snapshot
        original_issue_context = MODULE.github_issue_context

        def fake_snapshot(owner_repo, ref, timeout):
            self.assertEqual(owner_repo, "owner/agent-repo")
            return (
                "agent-repo",
                ["AGENTS.md", "Makefile"],
                {"Makefile": "test:\n\tpython -m unittest discover -s tests\n"},
            )

        def fake_issue_context(owner_repo, terms, limit, timeout):
            self.assertEqual(owner_repo, "owner/agent-repo")
            self.assertEqual(tuple(terms), ("message history", "tool output"))
            self.assertEqual(limit, 2)
            self.assertEqual(timeout, 7)
            return [
                {
                    "number": 42,
                    "title": "Resume drops tool output",
                    "state": "open",
                    "updated_at": "2026-05-31T00:00:00Z",
                    "url": "https://github.com/owner/agent-repo/issues/42",
                    "labels": ["bug", "resume"],
                    "matched_term": "resume",
                    "statebind_relevance": "Run/resume state boundary where serialized handles must retain their role.",
                }
            ]

        MODULE.github_snapshot = fake_snapshot
        MODULE.github_issue_context = fake_issue_context
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                markdown = root / "scout.md"
                result_card = root / "scout-card.md"
                context_card = root / "issue-context.md"
                feedback_packet = root / "feedback-packet.md"
                stdout = io.StringIO()
                with contextlib.redirect_stdout(stdout):
                    code = MODULE.run_scout(
                        [],
                        None,
                        ["owner/agent-repo"],
                        None,
                        None,
                        30,
                        7,
                        Path("statebind.json"),
                        Path("HANDOFF.md"),
                        Path(".github/workflows/statebind-guard.yml"),
                        None,
                        True,
                        markdown,
                        result_card,
                        None,
                        True,
                        context_card,
                        feedback_packet,
                        2,
                        ("message history", "tool output"),
                    )
                data = json.loads(stdout.getvalue())
                markdown_text = markdown.read_text()
                result_card_text = result_card.read_text()
                context_card_text = context_card.read_text()
                feedback_packet_text = feedback_packet.read_text()
        finally:
            MODULE.github_snapshot = original_snapshot
            MODULE.github_issue_context = original_issue_context

        self.assertEqual(code, 0)
        record = data["repositories"][0]
        self.assertEqual(record["issue_context"][0]["number"], 42)
        self.assertIn("public issue-context match", "; ".join(record["reasons"]))
        self.assertIn("Issue context", markdown_text)
        self.assertIn("Resume drops tool output", markdown_text)
        self.assertIn("Issue context", result_card_text)
        self.assertIn("# StateBind Scout Issue Context Card", context_card_text)
        self.assertIn("#42", context_card_text)
        self.assertIn("not treat it as", context_card_text)
        self.assertIn("# StateBind Maintainer Feedback Packet", feedback_packet_text)
        self.assertIn("Human final review is required", feedback_packet_text)
        self.assertIn("Feedback request: executable state-binding checks", feedback_packet_text)
        self.assertIn("I am asking for feedback, not proposing adoption", feedback_packet_text)

    def test_github_api_rate_limit_error_mentions_token(self):
        original_urlopen = MODULE.urlopen

        def fake_urlopen(req, timeout):
            raise MODULE.HTTPError(
                req.full_url,
                403,
                "Forbidden",
                hdrs=None,
                fp=io.BytesIO(b'{"message":"API rate limit exceeded"}'),
            )

        MODULE.urlopen = fake_urlopen
        try:
            with self.assertRaises(RuntimeError) as ctx:
                MODULE.github_api_json("https://api.github.com/repos/owner/repo", 3)
        finally:
            MODULE.urlopen = original_urlopen

        self.assertIn("GH_TOKEN", str(ctx.exception))
        self.assertIn("GITHUB_TOKEN", str(ctx.exception))

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
