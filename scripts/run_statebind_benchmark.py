#!/usr/bin/env python3
"""Run a StateBind Guard benchmark.

The benchmark is intentionally small and auditable. It measures one narrow
question: can a handoff checker distinguish executable role-handle bindings
from merely visible IDs, paths, commands, and URLs?
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "statebind_guard_seed_benchmark.json"
DEFAULT_CARD = ROOT / "docs" / "result_cards" / "statebind_guard_seed_benchmark.md"
DEFAULT_JSON = ROOT / "docs" / "result_cards" / "statebind_guard_seed_benchmark_metrics.json"


@dataclass(frozen=True)
class Binding:
    role: str
    handle: str


@dataclass
class Prediction:
    method: str
    record_id: str
    expected_pass: bool
    predicted_pass: bool


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"https?://", "", text)
    text = re.sub(r"[^a-z0-9./:#_-]+", " ", text)
    text = text.replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", text).strip()


def binding_from_dict(item: dict) -> Binding:
    return Binding(role=item["role"], handle=item["handle"])


def handle_visible(text: str, handle: str) -> bool:
    return normalize(handle) in normalize(text)


def role_visible(text: str, role: str) -> bool:
    role_norm = normalize(role)
    role_words = role_norm.split()
    text_norm = normalize(text)
    if role_norm in text_norm:
        return True
    return all(word in text_norm for word in role_words[-2:])


def line_binds(line: str, binding: Binding) -> bool:
    line_norm = normalize(line)
    return normalize(binding.role) in line_norm and normalize(binding.handle) in line_norm


def has_vague_resume(text: str) -> bool:
    vague_patterns = [
        "the file",
        "the test",
        "the command",
        "the sha above",
        "previous pr",
        "[fill in]",
    ]
    text_norm = normalize(text)
    return any(pattern in text_norm for pattern in vague_patterns)


def visibility_baseline(text: str, bindings: list[Binding]) -> bool:
    return all(handle_visible(text, binding.handle) for binding in bindings)


def keyword_role_baseline(text: str, bindings: list[Binding]) -> bool:
    return all(
        handle_visible(text, binding.handle) and role_visible(text, binding.role)
        for binding in bindings
    )


def statebind_guard(text: str, bindings: list[Binding]) -> bool:
    if has_vague_resume(text):
        return False
    lines = [line for line in text.splitlines() if line.strip()]
    return all(any(line_binds(line, binding) for line in lines) for binding in bindings)


METHODS: dict[str, Callable[[str, list[Binding]], bool]] = {
    "visibility_baseline": visibility_baseline,
    "keyword_role_baseline": keyword_role_baseline,
    "statebind_guard": statebind_guard,
}


def load_records(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def title_from_path(path: Path) -> str:
    stem = path.stem
    stem = stem.replace("statebind_guard_", "").replace("_benchmark", "")
    return stem.replace("_", " ").title()


def predict(records: list[dict]) -> list[Prediction]:
    predictions: list[Prediction] = []
    for record in records:
        bindings = [binding_from_dict(item) for item in record["required_bindings"]]
        expected_pass = record["label"] == "pass"
        for method, fn in METHODS.items():
            predictions.append(
                Prediction(
                    method=method,
                    record_id=record["id"],
                    expected_pass=expected_pass,
                    predicted_pass=fn(record["handoff"], bindings),
                )
            )
    return predictions


def summarize(predictions: list[Prediction]) -> dict[str, dict]:
    methods = sorted({prediction.method for prediction in predictions})
    summary: dict[str, dict] = {}
    for method in methods:
        rows = [prediction for prediction in predictions if prediction.method == method]
        tp = sum(p.expected_pass and p.predicted_pass for p in rows)
        tn = sum((not p.expected_pass) and (not p.predicted_pass) for p in rows)
        fp = sum((not p.expected_pass) and p.predicted_pass for p in rows)
        fn = sum(p.expected_pass and (not p.predicted_pass) for p in rows)
        total = len(rows)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        fail_count = fp + tn
        summary[method] = {
            "n": total,
            "accuracy": (tp + tn) / total if total else 0.0,
            "precision_accept": precision,
            "recall_accept": recall,
            "f1_accept": f1,
            "unsafe_accept_rate": fp / fail_count if fail_count else 0.0,
            "tp": tp,
            "tn": tn,
            "fp": fp,
            "fn": fn,
        }
    return summary


def category_counts(records: list[dict]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for record in records:
        category = record.get("category", "uncategorized")
        label = record.get("label", "")
        bucket = counts.setdefault(category, {"pass": 0, "fail": 0, "total": 0})
        bucket["total"] += 1
        if label in {"pass", "fail"}:
            bucket[label] += 1
    return dict(sorted(counts.items()))


def render_card(records: list[dict], summary: dict[str, dict], title: str) -> str:
    guard = summary["statebind_guard"]
    visibility = summary["visibility_baseline"]
    keyword = summary["keyword_role_baseline"]
    verdict = (
        "StateBind Guard beats both baselines on this benchmark."
        if guard["accuracy"] > max(visibility["accuracy"], keyword["accuracy"])
        and guard["unsafe_accept_rate"] < min(
            visibility["unsafe_accept_rate"], keyword["unsafe_accept_rate"]
        )
        else "StateBind Guard does not yet clear the benchmark gate."
    )

    lines = [
        f"# StateBind Guard {title} Benchmark",
        "",
        "## Hypothesis",
        "",
        "Merely preserving visible IDs, paths, commands, URLs, or SHAs is not enough",
        "for safe coding-agent handoff. A role-to-handle binding check should reduce",
        "unsafe acceptance of handoffs that mention the right handle but do not bind it",
        "to the active role.",
        "",
        "## Decision Gate",
        "",
        "Promote StateBind Guard as the first practical artifact only if it beats a",
        "visibility baseline and a keyword-role baseline while reducing unsafe accepts",
        "on failing handoffs.",
        "",
        "## Results",
        "",
        "| Method | Accuracy | Unsafe accept rate | Accept F1 | TP | TN | FP | FN |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for method in ["visibility_baseline", "keyword_role_baseline", "statebind_guard"]:
        row = summary[method]
        lines.append(
            f"| {method} | {row['accuracy']:.3f} | {row['unsafe_accept_rate']:.3f} | "
            f"{row['f1_accept']:.3f} | {row['tp']} | {row['tn']} | {row['fp']} | {row['fn']} |"
        )
    categories = category_counts(records)
    if categories:
        lines.extend(
            [
                "",
                "## Category Coverage",
                "",
                "| Category | Records | Pass | Fail |",
                "|---|---:|---:|---:|",
            ]
        )
        for category, counts in categories.items():
            lines.append(
                f"| {category} | {counts['total']} | {counts['pass']} | {counts['fail']} |"
            )
    if any(record.get("source_type") == "deployed" for record in records):
        scope_lines = [
            f"This benchmark contains {len(records)} sanitized, deployed-derived",
            "handoff snippets from real StateBind Guard release, CI, action,",
            "packaging, documentation, and adoption workflows. It preserves the",
            "role/handle structure while removing private local paths and secrets.",
        ]
    else:
        scope_lines = [
            f"This benchmark contains {len(records)} anonymized, real-shaped",
            "handoff snippets. It is designed to test the visible-but-unbound failure",
            "mode, not to claim broad deployed-agent coverage.",
        ]
    lines.extend(
        [
            "",
            "## Verdict",
            "",
            verdict,
            "",
            "## Scope",
            "",
            *scope_lines,
            "",
            "## Next Upgrade",
            "",
            "Collect natural handoffs from real Codex/Claude/OpenHands sessions and keep",
            "the same gate: fewer unsafe accepts than naive visibility and keyword baselines.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a StateBind Guard benchmark")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--card", type=Path, default=DEFAULT_CARD)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--title", help="human-readable benchmark title")
    args = parser.parse_args()

    records = load_records(args.data)
    predictions = predict(records)
    summary = summarize(predictions)
    title = args.title or title_from_path(args.data)
    data_path = str(args.data.relative_to(ROOT)) if args.data.is_relative_to(ROOT) else str(args.data)
    payload = {
        "data": data_path,
        "records": len(records),
        "category_counts": category_counts(records),
        "summary": summary,
        "predictions": [prediction.__dict__ for prediction in predictions],
    }

    args.card.parent.mkdir(parents=True, exist_ok=True)
    args.card.write_text(render_card(records, summary, title), encoding="utf-8")
    args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(render_card(records, summary, title))
    print(f"Wrote {args.card}")
    print(f"Wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
