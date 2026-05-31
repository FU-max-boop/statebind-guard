import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_statebind_benchmark.py"


def load_module():
    spec = importlib.util.spec_from_file_location("run_statebind_benchmark", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class StateBindBenchmarkTests(unittest.TestCase):
    def test_guard_beats_baselines_on_seed_benchmark(self):
        module = load_module()
        records = module.load_records(module.DEFAULT_DATA)
        summary = module.summarize(module.predict(records))

        guard = summary["statebind_guard"]
        visibility = summary["visibility_baseline"]
        keyword = summary["keyword_role_baseline"]

        self.assertGreater(guard["accuracy"], visibility["accuracy"])
        self.assertGreater(guard["accuracy"], keyword["accuracy"])
        self.assertLess(guard["unsafe_accept_rate"], visibility["unsafe_accept_rate"])
        self.assertLess(guard["unsafe_accept_rate"], keyword["unsafe_accept_rate"])

    def test_guard_beats_baselines_on_natural_handoff_benchmark(self):
        module = load_module()
        records = module.load_records(ROOT / "data" / "statebind_guard_natural_handoff_benchmark.json")
        summary = module.summarize(module.predict(records))

        guard = summary["statebind_guard"]
        visibility = summary["visibility_baseline"]
        keyword = summary["keyword_role_baseline"]

        self.assertGreaterEqual(guard["accuracy"], 0.95)
        self.assertGreater(guard["accuracy"], visibility["accuracy"])
        self.assertGreater(guard["accuracy"], keyword["accuracy"])
        self.assertLess(guard["unsafe_accept_rate"], visibility["unsafe_accept_rate"])
        self.assertLess(guard["unsafe_accept_rate"], keyword["unsafe_accept_rate"])

    def test_failure_corpus_has_broad_coverage_and_guard_clears_gate(self):
        module = load_module()
        records = module.load_records(ROOT / "data" / "statebind_guard_failure_corpus.json")
        summary = module.summarize(module.predict(records))
        categories = module.category_counts(records)

        self.assertGreaterEqual(len(records), 30)
        self.assertGreaterEqual(len(categories), 8)
        self.assertTrue(all(counts["pass"] >= 1 and counts["fail"] >= 1 for counts in categories.values()))

        guard = summary["statebind_guard"]
        visibility = summary["visibility_baseline"]
        keyword = summary["keyword_role_baseline"]

        self.assertGreaterEqual(guard["accuracy"], 0.95)
        self.assertGreater(guard["accuracy"], visibility["accuracy"])
        self.assertGreater(guard["accuracy"], keyword["accuracy"])
        self.assertLessEqual(guard["unsafe_accept_rate"], 0.05)
        self.assertLess(guard["unsafe_accept_rate"], visibility["unsafe_accept_rate"])
        self.assertLess(guard["unsafe_accept_rate"], keyword["unsafe_accept_rate"])

    def test_deployed_corpus_has_provenance_and_guard_clears_gate(self):
        module = load_module()
        records = module.load_records(ROOT / "data" / "statebind_guard_deployed_corpus.json")
        summary = module.summarize(module.predict(records))
        categories = module.category_counts(records)

        self.assertGreaterEqual(len(records), 20)
        self.assertGreaterEqual(len(categories), 8)
        self.assertTrue(all(record.get("source_type") == "deployed" for record in records))
        self.assertTrue(all(record.get("source_event") for record in records))
        self.assertTrue(all(counts["pass"] >= 1 and counts["fail"] >= 1 for counts in categories.values()))

        guard = summary["statebind_guard"]
        visibility = summary["visibility_baseline"]
        keyword = summary["keyword_role_baseline"]

        self.assertGreaterEqual(guard["accuracy"], 0.95)
        self.assertGreater(guard["accuracy"], visibility["accuracy"])
        self.assertGreater(guard["accuracy"], keyword["accuracy"])
        self.assertLessEqual(guard["unsafe_accept_rate"], 0.05)
        self.assertLess(guard["unsafe_accept_rate"], visibility["unsafe_accept_rate"])
        self.assertLess(guard["unsafe_accept_rate"], keyword["unsafe_accept_rate"])

    def test_github_scout_campaign_card_is_backed_by_data(self):
        data = json.loads((ROOT / "data" / "statebind_guard_github_scout_campaign_2026_05_31.json").read_text())
        card = (ROOT / "docs" / "result_cards" / "statebind_guard_github_scout_campaign_2026_05_31.md").read_text()
        records = data["repositories"]

        self.assertEqual(data["summary"], {"total": 8, "ok": 8, "errors": 0})
        self.assertEqual(sum(1 for record in records if record["priority"] == "high"), 7)
        self.assertEqual(sum(1 for record in records if record["priority"] == "skip"), 1)
        self.assertIn("repositories scanned: 8", card)
        self.assertIn("| `high` | 7 |", card)
        self.assertIn("generated maintainer-note drafts: 7", card)
        self.assertIn("openai-agents-python", card)
        self.assertIn("pydantic-ai", card)
        self.assertIn("triage artifact", card)

    def test_adoption_target_review_has_human_gate(self):
        data = json.loads((ROOT / "data" / "statebind_guard_adoption_target_review_2026_05_31.json").read_text())
        doc = (ROOT / "docs" / "adoption_target_review_2026_05_31.md").read_text()
        targets = data["targets"]

        self.assertEqual(data["summary"], {"reviewed": 5, "go_feedback_only": 2, "hold_more_evidence": 3, "skip": 0})
        self.assertEqual(sum(1 for target in targets if target["decision"] == "go_feedback_only"), 2)
        self.assertEqual(sum(1 for target in targets if target["decision"] == "hold_more_evidence"), 3)
        self.assertTrue(all(target["do_not_do"] for target in targets))
        self.assertIn("pydantic/pydantic-ai", doc)
        self.assertIn("openai/openai-agents-python", doc)
        self.assertIn("Human final review is required", doc)

    def test_adoption_feedback_requests_are_rendered_from_review(self):
        doc = (ROOT / "docs" / "adoption_feedback_requests_2026_05_31.md").read_text()
        self.assertIn("Draft For `pydantic/pydantic-ai`", doc)
        self.assertIn("Draft For `openai/openai-agents-python`", doc)
        self.assertIn("adoption_context_evidence_2026_05_31.md", doc)
        self.assertIn("including #5731 and #5721", doc)
        self.assertIn("including #3319 and #3004", doc)
        self.assertIn("Would a StateBind-style executable handoff contract", doc)
        self.assertIn("Would executable binding checks be useful", doc)
        self.assertIn("Human final review", doc)
        self.assertNotIn("Draft For `browser-use/browser-use`", doc)
        self.assertNotIn("Ask whether", doc)

        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "feedback.md"
            subprocess.check_call(
                [
                    "python",
                    "scripts/render_adoption_feedback_requests.py",
                    "--review",
                    "data/statebind_guard_adoption_target_review_2026_05_31.json",
                    "--context",
                    "data/statebind_guard_adoption_context_evidence_2026_05_31.json",
                    "--out",
                    str(out),
                ],
                cwd=ROOT,
            )
            rendered = out.read_text()
            self.assertIn("go_feedback_only", rendered)
            self.assertIn("Hold Targets", rendered)
            self.assertIn("adoption_context_evidence_2026_05_31.md", rendered)

    def test_adoption_context_evidence_is_rendered_from_data(self):
        data = json.loads((ROOT / "data" / "statebind_guard_adoption_context_evidence_2026_05_31.json").read_text())
        doc = (ROOT / "docs" / "adoption_context_evidence_2026_05_31.md").read_text()

        self.assertEqual(data["schema_version"], "0.1")
        self.assertEqual(len(data["targets"]), 2)
        self.assertTrue(all(target["outreach_decision"] == "go_feedback_only" for target in data["targets"]))
        self.assertTrue(all(len(target["evidence_items"]) >= 4 for target in data["targets"]))
        self.assertIn("pydantic/pydantic-ai", doc)
        self.assertIn("openai/openai-agents-python", doc)
        self.assertIn("#5731", doc)
        self.assertIn("#3004", doc)
        self.assertIn("not evidence that maintainers want StateBind Guard", doc)

        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "context.md"
            subprocess.check_call(
                [
                    "python",
                    "scripts/render_adoption_context_evidence.py",
                    "--data",
                    "data/statebind_guard_adoption_context_evidence_2026_05_31.json",
                    "--out",
                    str(out),
                ],
                cwd=ROOT,
            )
            rendered = out.read_text()
            self.assertIn("Target Summary", rendered)
            self.assertIn("draft_anchor", rendered)

    def test_pydantic_feedback_packet_has_strict_gate(self):
        packet = (ROOT / "docs" / "maintainer_feedback" / "pydantic_ai_feedback_packet_2026_05_31.md").read_text()
        self.assertIn("Human final review is required", packet)
        self.assertIn("#5731", packet)
        self.assertIn("#5721", packet)
        self.assertIn("--issue-context-term", packet)
        self.assertIn("I am not asking you to add a dependency", packet)
        self.assertIn("Do not imply StateBind Guard is a fix", packet)


if __name__ == "__main__":
    unittest.main()
