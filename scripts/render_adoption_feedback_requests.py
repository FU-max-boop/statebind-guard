#!/usr/bin/env python3
"""Render maintainer-feedback drafts from a reviewed StateBind target packet."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REVIEW = ROOT / "data" / "statebind_guard_adoption_target_review_2026_05_31.json"
DEFAULT_OUT = ROOT / "docs" / "adoption_feedback_requests_2026_05_31.md"


def markdown_cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "\\|")


def repo_short_name(repo: str) -> str:
    return repo.rsplit("/", 1)[-1]


def sentence_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def load_review(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def render_feedback_draft(target: dict[str, Any]) -> str:
    repo = target["repo"]
    short = repo_short_name(repo)
    evidence = ", ".join(f"`{path}`" for path in target["evidence_paths"])
    title = f"Feedback request: executable handoff boundaries in `{short}`"
    body = f"""### Draft For `{repo}`

**Suggested title:** {title}

```text
Hi {short} maintainers,

I maintain StateBind Guard, a small open-source checker for one coding-agent
handoff failure mode: a transcript or summary can contain the right file, test,
pull request, or commit, but still fail to preserve which handle is bound to the
active role the next agent must act on.

I ran a read-only StateBind scout and then did a human review before deciding
whether to ask for feedback here. The relevant surfaces I saw were {evidence}.

I am not asking you to adopt a dependency or wire CI. My narrow question is:
{target.get("draft_question", target["first_ask"])}

If this is not a problem you want surfaced, that is useful feedback too. If it
is relevant, what would be the least noisy artifact for maintainers to review:
a short issue template, a docs-only checklist, a CI warning, or something else?
```

**Why this target is cleared for feedback:** {target["why_it_fits"]}

**Do not do:**
{sentence_list(target["do_not_do"])}
"""
    return body


def render_review_markdown(review: dict[str, Any]) -> str:
    go_targets = [target for target in review["targets"] if target["decision"] == "go_feedback_only"]
    hold_targets = [target for target in review["targets"] if target["decision"] != "go_feedback_only"]
    lines = [
        "# Adoption Feedback Requests: 2026-05-31",
        "",
        "These are human-reviewed feedback-only drafts generated from",
        f"`{review['source_campaign']}` and the target-review packet.",
        "",
        "They are intentionally not ready-to-post automation. A human should read",
        "the current repository context, trim wording, and only then decide whether",
        "to publish from their own account.",
        "",
        "## Posting Gate",
        "",
    ]
    lines.extend(f"- {rule}" for rule in review["review_gate"])
    lines.extend(
        [
        "- Do not post any draft whose target review decision is not `go_feedback_only`.",
        "- Do not include generated text verbatim if it sounds broader than the maintainer's actual problem.",
        "- Human final review is required before posting any public comment.",
        "",
        "## Draft Summary",
            "",
            "| Repository | Decision | Confidence | Evidence |",
            "|---|---|---|---|",
        ]
    )
    for target in go_targets:
        lines.append(
            "| `{repo}` | `{decision}` | {confidence} | {evidence} |".format(
                repo=target["repo"],
                decision=target["decision"],
                confidence=target["confidence"],
                evidence=markdown_cell(", ".join(target["evidence_paths"])),
            )
        )

    lines.extend(["", "## Feedback-Only Drafts", ""])
    for target in go_targets:
        lines.append(render_feedback_draft(target).rstrip())
        lines.append("")

    lines.extend(
        [
            "## Hold Targets",
            "",
            "| Repository | Decision | Evidence Needed |",
            "|---|---|---|",
        ]
    )
    for target in hold_targets:
        lines.append(
            "| `{repo}` | `{decision}` | {ask} |".format(
                repo=target["repo"],
                decision=target["decision"],
                ask=markdown_cell(target["first_ask"]),
            )
        )

    lines.extend(
        [
            "",
            "## Manual Closeout Checklist",
            "",
            "- Re-check the target repository's current issues and contribution rules.",
            "- Remove any claim that cannot be tied to a specific target path or doc.",
            "- Keep the ask to feedback, not adoption.",
            "- Record any maintainer reply as an external signal only after it exists publicly.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render StateBind adoption feedback drafts")
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    review = load_review(args.review)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_review_markdown(review), encoding="utf-8")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
