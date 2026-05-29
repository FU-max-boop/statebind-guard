import importlib.util
import sys
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


if __name__ == "__main__":
    unittest.main()
