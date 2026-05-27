#!/usr/bin/env python3
"""Generate or check a lightweight StateBind coding-agent handoff.

This script is intentionally dependency-free. It produces a draft handoff;
Codex or a human should still verify evidence and confidence.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable


FILE_RE = re.compile(r"(?<![\w./-])(?:[\w.-]+/)+[\w.@:+-]+(?:\.[A-Za-z0-9_+-]+)?")
TEST_SELECTOR_RE = re.compile(r"(?:pytest|python -m pytest)\s+[^\n\r`]+")
COMMAND_RE = re.compile(r"(?m)^\s*(?:\$ )?((?:pytest|python -m pytest|npm test|pnpm test|yarn test|uv run|python|node|make|git)\b[^\n\r]*)")
SHA_RE = re.compile(r"\b[0-9a-f]{7,40}\b")
URL_RE = re.compile(r"https?://[^\s)>\"]+")


@dataclass
class Binding:
    role: str
    handle: str
    evidence: str
    confidence: str = "medium"
    risk: str = ""


def run(cmd: list[str], cwd: Path) -> str:
    try:
        return subprocess.check_output(cmd, cwd=str(cwd), stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return ""


def uniq(items: Iterable[str], limit: int = 20) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        item = item.strip().strip(".,;:")
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def clean_command(text: str) -> str:
    """Trim a command captured from prose without trying to parse every shell."""
    text = text.strip()
    text = re.split(
        r"\s+(?:before handoff|before resuming|before continuing|Related|Base sha|base sha|Head sha|head sha|PR\s+https?://|Issue\s+https?://)",
        text,
        maxsplit=1,
    )[0]
    return text.rstrip(".,; ")


def read_text(path: Path | None) -> str:
    if not path:
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def collect(repo: Path, transcript: Path | None, repo_label: str | None = None, transcript_label: str | None = None) -> dict:
    text = read_text(transcript)
    branch = run(["git", "branch", "--show-current"], repo)
    status = run(["git", "status", "--short"], repo)
    diff_files = uniq(run(["git", "diff", "--name-only"], repo).splitlines(), limit=50)
    staged_files = uniq(run(["git", "diff", "--cached", "--name-only"], repo).splitlines(), limit=50)
    recent_commit = run(["git", "rev-parse", "--short", "HEAD"], repo)

    paths = uniq(FILE_RE.findall(text), limit=50)
    commands = uniq([clean_command(m.group(1)) for m in COMMAND_RE.finditer(text)], limit=20)
    tests = uniq([clean_command(m) for m in TEST_SELECTOR_RE.findall(text)], limit=20)
    shas = uniq(SHA_RE.findall(text), limit=20)
    urls = uniq(URL_RE.findall(text), limit=20)

    return {
        "_repo_path": str(repo.resolve()),
        "repo": repo_label or str(repo.resolve()),
        "transcript": transcript_label or (str(transcript.resolve()) if transcript else ""),
        "branch": branch,
        "status": status,
        "diff_files": diff_files,
        "staged_files": staged_files,
        "recent_commit": recent_commit,
        "paths": paths,
        "commands": commands,
        "tests": tests,
        "shas": shas,
        "urls": urls,
    }


def build_bindings(data: dict) -> list[Binding]:
    bindings: list[Binding] = []
    if data["repo"]:
        bindings.append(Binding("working_directory", data["repo"], "local repo path", "high"))
    if data["branch"]:
        bindings.append(Binding("branch", data["branch"], "git branch --show-current", "high"))
    for p in data["diff_files"][:10]:
        bindings.append(Binding("modified_file", p, "git diff --name-only", "high"))
    for p in data["staged_files"][:10]:
        bindings.append(Binding("staged_file", p, "git diff --cached --name-only", "high"))
    for t in data["tests"][:5]:
        bindings.append(Binding("failing_or_relevant_test", t, "transcript pytest command", "medium", "verify still failing"))
    for c in data["commands"][:8]:
        bindings.append(Binding("candidate_next_command", c, "transcript command line", "medium", "verify before running"))
    for u in data["urls"][:8]:
        role = "related_pr_or_issue" if "github.com" in u else "related_url"
        bindings.append(Binding(role, u, "transcript URL", "medium"))
    for s in data["shas"][:8]:
        bindings.append(Binding("candidate_commit_sha", s, "transcript SHA-like token", "low", "verify role: head/base/stale"))
    for p in data["paths"][:12]:
        if p not in data["diff_files"] and p not in data["staged_files"]:
            repo_path = data.get("_repo_path") or data.get("repo")
            exists = (Path(repo_path) / p).exists() if repo_path else False
            bindings.append(Binding("candidate_path", p, "transcript path mention", "medium" if exists else "low", "" if exists else "unverified_handle"))
    return bindings


def risks(data: dict, bindings: list[Binding]) -> list[str]:
    out: list[str] = []
    roles = {b.role for b in bindings}
    if "modified_file" not in roles and "staged_file" not in roles:
        out.append("No modified/staged files detected from git; verify the active patch target.")
    if not any(b.role in {"failing_or_relevant_test", "candidate_next_command"} for b in bindings):
        out.append("No executable test/command found; add an exact next command before resuming.")
    if len([b for b in bindings if b.role == "candidate_commit_sha"]) > 1:
        out.append("Multiple SHA-like handles detected; bind each to head/base/stale/current before use.")
    if any(b.risk == "unverified_handle" for b in bindings):
        out.append("Some path handles were mentioned in text but not found locally.")
    return out


def to_contract(data: dict) -> dict:
    bindings = build_bindings(data)
    rs = risks(data, bindings)
    raw_signals = {k: v for k, v in data.items() if not k.startswith("_")}
    prompt = (
        "You are resuming a coding-agent task. First read HANDOFF.md and statebind.json. "
        "Verify the working directory, branch, files, and commands before editing. "
        "Only act on explicitly bound handles unless newer evidence contradicts them. "
        "If any handle is missing or ambiguous, pause and repair the handoff."
    )
    return {
        "task": {"goal": "", "status": "draft handoff generated from repo/transcript"},
        "active_target": {"type": "", "handle": "", "evidence": "", "confidence": "uncertain"},
        "bindings": [asdict(b) for b in bindings],
        "risks": rs,
        "resume_prompt": prompt,
        "raw_signals": raw_signals,
    }


def render_md(contract: dict) -> str:
    lines: list[str] = []
    lines.append("# Agent Handoff")
    lines.append("")
    lines.append("## Task")
    lines.append(f"- Goal: {contract['task'].get('goal') or '[fill in]'}")
    lines.append(f"- Current status: {contract['task'].get('status')}")
    lines.append("")
    lines.append("## Active Target")
    at = contract["active_target"]
    lines.append(f"- Type: {at.get('type') or '[fill in]'}")
    lines.append(f"- Handle: {at.get('handle') or '[fill in]'}")
    lines.append(f"- Evidence: {at.get('evidence') or '[fill in]'}")
    lines.append(f"- Confidence: {at.get('confidence')}")
    lines.append("")
    lines.append("## Executable Bindings")
    lines.append("")
    lines.append("| Role | Handle | Evidence | Confidence | Risk |")
    lines.append("|---|---|---|---|---|")
    for b in contract["bindings"]:
        lines.append(f"| {b['role']} | `{b['handle']}` | {b['evidence']} | {b['confidence']} | {b.get('risk','')} |")
    lines.append("")
    lines.append("## Next Action")
    lines.append("1. Verify this handoff against current repo state.")
    lines.append("2. Fill in active target and remove stale candidate bindings.")
    lines.append("3. Run only verified commands.")
    lines.append("")
    lines.append("## Risks And Ambiguities")
    for r in contract["risks"] or ["[none recorded]"]:
        lines.append(f"- {r}")
    lines.append("")
    lines.append("## Resume Prompt")
    lines.append("")
    lines.append("> " + contract["resume_prompt"])
    lines.append("")
    return "\n".join(lines)


def check_handoff(path: Path) -> int:
    text = path.read_text(encoding="utf-8", errors="replace")
    required = ["Active Target", "Executable Bindings", "Next Action", "Risks"]
    missing = [h for h in required if h.lower() not in text.lower()]
    vague = [w for w in ["the file", "the test", "the command", "the PR", "previous command"] if w in text]
    print(f"Checked: {path}")
    if missing:
        print("Missing sections:", ", ".join(missing))
    if vague:
        print("Vague phrases to replace with exact handles:", ", ".join(vague))
    if not missing and not vague:
        print("Basic handoff check passed. Still verify evidence manually.")
    return 1 if missing or vague else 0


def write_demo() -> str:
    return """# Demo: Visible ID But Unbound

Context mentions both:
- head SHA: `abc1234`
- base SHA: `def5678`
- stale SHA: `999aaaa`

Bad summary:
> Continue from the PR and use the SHA above.

StateBind handoff:

| Role | Handle | Evidence | Confidence | Risk |
|---|---|---|---|---|
| active_target | PR #42 | GitHub PR URL in transcript | high | |
| comparison_base_sha | `def5678` | PR metadata row `base.sha` | high | do not use head SHA |
| current_head_sha | `abc1234` | PR metadata row `head.sha` | high | wrong role for comparison |

Resume rule:
Use `def5678` only for the comparison-base role. Do not infer from visibility alone.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="StateBind handoff helper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_extract = sub.add_parser("extract", help="generate HANDOFF.md/statebind.json draft")
    p_extract.add_argument("--repo", type=Path, default=Path("."))
    p_extract.add_argument("--transcript", type=Path)
    p_extract.add_argument("--out", type=Path, default=Path("HANDOFF.md"))
    p_extract.add_argument("--json", type=Path, default=Path("statebind.json"))
    p_extract.add_argument("--repo-label", help="portable label to write instead of an absolute repo path")
    p_extract.add_argument("--transcript-label", help="portable label to write instead of an absolute transcript path")

    p_check = sub.add_parser("check", help="basic handoff audit")
    p_check.add_argument("handoff", type=Path)

    sub.add_parser("demo", help="print visible-but-unbound demo")

    args = parser.parse_args()
    if args.cmd == "extract":
        repo = args.repo.resolve()
        contract = to_contract(collect(repo, args.transcript, args.repo_label, args.transcript_label))
        args.out.write_text(render_md(contract), encoding="utf-8")
        args.json.write_text(json.dumps(contract, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote {args.out} and {args.json}")
        print("Draft only: verify evidence and remove stale/uncertain candidates before resuming.")
        return 0
    if args.cmd == "check":
        return check_handoff(args.handoff)
    if args.cmd == "demo":
        print(write_demo())
        return 0
    raise AssertionError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main())
