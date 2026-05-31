#!/usr/bin/env python3
"""Render public issue-context evidence for StateBind feedback outreach."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "statebind_guard_adoption_context_evidence_2026_05_31.json"
DEFAULT_OUT = ROOT / "docs" / "adoption_context_evidence_2026_05_31.md"


def markdown_cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "\\|")


def issue_link(item: dict[str, Any]) -> str:
    return f"[#{item['number']}]({item['url']})"


def load_evidence(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def render_evidence_markdown(data: dict[str, Any]) -> str:
    lines = [
        "# Adoption Context Evidence: 2026-05-31",
        "",
        "This is a pre-posting evidence card for StateBind Guard feedback-only",
        "outreach. It records current public issue context so maintainer-facing",
        "questions stay specific instead of generic.",
        "",
        f"**Source:** {data['source']}",
        "",
        f"**Claim boundary:** {data['claim_boundary']}",
        "",
        "## Posting Gate",
        "",
    ]
    lines.extend(f"- {rule}" for rule in data["posting_gate"])

    lines.extend(
        [
            "",
            "## Target Summary",
            "",
            "| Repository | Decision | Issue Context | Current Read |",
            "|---|---|---:|---|",
        ]
    )
    for target in data["targets"]:
        lines.append(
            "| `{repo}` | `{decision}` | {count} issues | {read} |".format(
                repo=target["repo"],
                decision=target["outreach_decision"],
                count=len(target["evidence_items"]),
                read=markdown_cell(target["current_read"]),
            )
        )

    for target in data["targets"]:
        lines.extend(
            [
                "",
                f"## `{target['repo']}`",
                "",
                target["current_read"],
                "",
                "**Draft context sentence:**",
                "",
                f"> {target['draft_context']}",
                "",
                "| Issue | State | Labels | StateBind Relevance | Outreach Use |",
                "|---|---|---|---|---|",
            ]
        )
        for item in target["evidence_items"]:
            lines.append(
                "| {issue} {title} | `{state}` | {labels} | {relevance} | `{use}` |".format(
                    issue=issue_link(item),
                    title=markdown_cell(item["title"]),
                    state=item["state"].lower(),
                    labels=markdown_cell(", ".join(item["labels"]) if item["labels"] else "none"),
                    relevance=markdown_cell(item["statebind_relevance"]),
                    use=item["outreach_use"],
                )
            )

    lines.extend(
        [
            "",
            "## Closeout Rule",
            "",
            "If any target issue changes materially before posting, regenerate or manually",
            "refresh this card. Treat stale context as a reason to hold outreach, not as",
            "permission to post a generic note.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render StateBind adoption context evidence")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    data = load_evidence(args.data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_evidence_markdown(data), encoding="utf-8")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
