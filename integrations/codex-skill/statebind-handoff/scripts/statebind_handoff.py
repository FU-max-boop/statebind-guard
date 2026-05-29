#!/usr/bin/env python3
"""Generate, check, and validate StateBind coding-agent handoffs.

This script is intentionally dependency-free. It produces a draft handoff;
Codex or a human should still verify evidence and confidence.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable


FILE_RE = re.compile(r"(?<![\w./-])(?:[\w.-]+/)+[\w.@:+-]+(?:\.[A-Za-z0-9_+-]+)?")
TEST_SELECTOR_RE = re.compile(r"(?:pytest|python -m pytest)\s+[^\n\r`]+")
COMMAND_RE = re.compile(r"(?m)^\s*(?:\$ )?((?:pytest|python -m pytest|npm test|pnpm test|yarn test|uv run|python|node|make|git)\b[^\n\r]*)")
SHA_RE = re.compile(r"\b[0-9a-f]{7,40}\b")
URL_RE = re.compile(r"https?://[^\s)>\"]+")
CONFIDENCE_VALUES = {"high", "medium", "low", "uncertain"}
VAGUE_HANDLE_RE = re.compile(r"\b(the|that|this|previous|above|same)\s+(file|test|command|pr|issue|sha|commit|branch)\b", re.I)
COMMAND_PREFIXES = (
    "pytest",
    "python -m pytest",
    "npm test",
    "pnpm test",
    "yarn test",
    "uv run",
    "python",
    "node",
    "make",
    "git",
)
SCHEMA_VERSION = "0.1"
STATEBIND_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://github.com/FU-max-boop/statebind-guard/schemas/statebind.schema.json",
    "title": "StateBind handoff contract",
    "type": "object",
    "required": ["schema_version", "task", "active_target", "bindings"],
    "properties": {
        "schema_version": {"type": "string", "enum": [SCHEMA_VERSION]},
        "task": {
            "type": "object",
            "required": ["goal", "status"],
            "properties": {
                "goal": {"type": "string"},
                "status": {"type": "string"},
            },
            "additionalProperties": True,
        },
        "active_target": {
            "type": "object",
            "required": ["type", "handle", "evidence", "confidence"],
            "properties": {
                "type": {"type": "string"},
                "handle": {"type": "string"},
                "evidence": {"type": "string"},
                "confidence": {"$ref": "#/$defs/confidence"},
            },
            "additionalProperties": True,
        },
        "bindings": {
            "type": "array",
            "items": {"$ref": "#/$defs/binding"},
        },
        "risks": {
            "type": "array",
            "items": {"type": "string"},
        },
        "resume_prompt": {"type": "string"},
        "raw_signals": {"type": "object"},
    },
    "$defs": {
        "confidence": {"type": "string", "enum": sorted(CONFIDENCE_VALUES)},
        "binding": {
            "type": "object",
            "required": ["role", "handle", "evidence", "confidence", "risk"],
            "properties": {
                "role": {"type": "string"},
                "handle": {"type": "string"},
                "evidence": {"type": "string"},
                "confidence": {"$ref": "#/$defs/confidence"},
                "risk": {"type": "string"},
            },
            "additionalProperties": True,
        },
    },
    "additionalProperties": True,
}


@dataclass
class Binding:
    role: str
    handle: str
    evidence: str
    confidence: str = "medium"
    risk: str = ""


@dataclass
class ValidationFinding:
    severity: str
    code: str
    message: str
    role: str = ""
    handle: str = ""


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
        if "::" in p:
            continue
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
        "schema_version": SCHEMA_VERSION,
        "task": {"goal": "", "status": "draft handoff generated from repo/transcript"},
        "active_target": {"type": "", "handle": "", "evidence": "", "confidence": "uncertain"},
        "bindings": [asdict(b) for b in bindings],
        "risks": rs,
        "resume_prompt": prompt,
        "raw_signals": raw_signals,
    }


def is_blank(value: Any) -> bool:
    return value is None or str(value).strip() in {"", "[fill in]"}


def looks_like_path(handle: str) -> bool:
    if "://" in handle:
        return False
    if handle.startswith(("-", "$", *COMMAND_PREFIXES)):
        return False
    return "/" in handle or bool(re.search(r"\.[A-Za-z0-9_+-]{1,8}$", handle))


def is_action_role(role: str) -> bool:
    role = role.lower()
    return any(token in role for token in ("command", "test", "next_action", "failing"))


def add_finding(
    findings: list[ValidationFinding],
    severity: str,
    code: str,
    message: str,
    role: str = "",
    handle: str = "",
) -> None:
    findings.append(ValidationFinding(severity, code, message, role, handle))


def validate_contract(contract: dict[str, Any], repo: Path | None = None) -> list[ValidationFinding]:
    """Validate the machine-readable StateBind contract.

    The validator is intentionally conservative: it checks structure and
    executability signals without pretending to prove semantic correctness.
    """
    findings: list[ValidationFinding] = []

    if not isinstance(contract, dict):
        return [ValidationFinding("error", "contract_not_object", "StateBind contract must be a JSON object.")]

    schema_version = str(contract.get("schema_version", "")).strip()
    if not schema_version:
        add_finding(findings, "error", "missing_schema_version", "`schema_version` is required.")
    elif schema_version != SCHEMA_VERSION:
        add_finding(
            findings,
            "error",
            "unsupported_schema_version",
            f"`schema_version` {schema_version!r} is not supported by this validator; expected {SCHEMA_VERSION!r}.",
        )

    task = contract.get("task")
    if not isinstance(task, dict):
        add_finding(findings, "error", "missing_task", "Missing `task` object.")
    elif is_blank(task.get("goal")):
        add_finding(findings, "warning", "blank_task_goal", "Task goal is blank; fill it before handoff consumption.")

    active_target = contract.get("active_target")
    if not isinstance(active_target, dict):
        add_finding(findings, "error", "missing_active_target", "Missing `active_target` object.")
    else:
        for field in ("type", "handle", "evidence"):
            if is_blank(active_target.get(field)):
                add_finding(
                    findings,
                    "warning",
                    f"blank_active_target_{field}",
                    f"Active target `{field}` is blank; bind the current object before resuming.",
                )
        confidence = str(active_target.get("confidence", "")).strip()
        if confidence and confidence not in CONFIDENCE_VALUES:
            add_finding(
                findings,
                "error",
                "invalid_active_target_confidence",
                f"Active target confidence `{confidence}` is not one of {sorted(CONFIDENCE_VALUES)}.",
            )

    bindings = contract.get("bindings")
    if not isinstance(bindings, list):
        add_finding(findings, "error", "missing_bindings", "`bindings` must be a list.")
        bindings = []
    elif not bindings:
        add_finding(findings, "error", "empty_bindings", "`bindings` is empty; no executable state is preserved.")

    seen_pairs: set[tuple[str, str]] = set()
    exact_action_count = 0
    low_or_uncertain_without_risk = 0

    for idx, raw in enumerate(bindings):
        if not isinstance(raw, dict):
            add_finding(findings, "error", "binding_not_object", f"Binding #{idx} must be an object.")
            continue

        role = str(raw.get("role", "")).strip()
        handle = str(raw.get("handle", "")).strip()
        evidence = str(raw.get("evidence", "")).strip()
        confidence = str(raw.get("confidence", "")).strip()
        risk = str(raw.get("risk", "")).strip()

        if is_blank(role):
            add_finding(findings, "error", "blank_binding_role", f"Binding #{idx} has a blank role.")
        if is_blank(handle):
            add_finding(findings, "error", "blank_binding_handle", f"Binding #{idx} has a blank handle.", role)
        if is_blank(evidence):
            add_finding(findings, "error", "blank_binding_evidence", f"Binding `{role}` has blank evidence.", role, handle)

        if confidence not in CONFIDENCE_VALUES:
            add_finding(
                findings,
                "error",
                "invalid_binding_confidence",
                f"Binding `{role}` confidence `{confidence}` is not one of {sorted(CONFIDENCE_VALUES)}.",
                role,
                handle,
            )

        if VAGUE_HANDLE_RE.search(handle):
            add_finding(
                findings,
                "error",
                "vague_handle",
                "Handle uses vague reference language; replace it with an exact executable handle.",
                role,
                handle,
            )

        pair = (role, handle)
        if pair in seen_pairs:
            add_finding(findings, "warning", "duplicate_binding", "Duplicate role/handle binding.", role, handle)
        seen_pairs.add(pair)

        if confidence in {"low", "uncertain"} and not risk:
            low_or_uncertain_without_risk += 1
            add_finding(
                findings,
                "warning",
                "uncertain_without_risk",
                "Low/uncertain binding should explain the ambiguity in `risk`.",
                role,
                handle,
            )

        if is_action_role(role):
            exact_action_count += 1
            if not handle.startswith(COMMAND_PREFIXES):
                add_finding(
                    findings,
                    "warning",
                    "action_handle_not_command_like",
                    "Action/test role should usually bind to an exact command or pytest selector.",
                    role,
                    handle,
                )

        if repo and looks_like_path(handle):
            candidate = (repo / handle).resolve()
            try:
                candidate.relative_to(repo.resolve())
            except ValueError:
                add_finding(findings, "error", "path_escapes_repo", "Path handle escapes the repository root.", role, handle)
            else:
                if not candidate.exists() and "unverified" not in risk.lower():
                    add_finding(
                        findings,
                        "warning",
                        "path_not_found",
                        "Path-like handle does not exist in the repository; mark risk if this is expected.",
                        role,
                        handle,
                    )

    if exact_action_count == 0:
        add_finding(
            findings,
            "warning",
            "no_action_binding",
            "No test/command/next-action binding found; resuming agents may know context but not what to execute.",
        )

    risks_value = contract.get("risks", [])
    if low_or_uncertain_without_risk and not risks_value:
        add_finding(
            findings,
            "warning",
            "missing_risk_summary",
            "Low/uncertain bindings exist but the top-level risk summary is empty.",
        )

    return findings


def render_validation_text(findings: list[ValidationFinding]) -> str:
    if not findings:
        return "StateBind validation passed: no structural findings."
    lines = ["StateBind validation findings:"]
    for finding in findings:
        target = f" role={finding.role!r} handle={finding.handle!r}" if finding.role or finding.handle else ""
        lines.append(f"- [{finding.severity}] {finding.code}:{target} {finding.message}")
    return "\n".join(lines)


def validation_exit_code(findings: list[ValidationFinding], fail_on: str) -> int:
    severities = {f.severity for f in findings}
    if fail_on == "warning":
        return 1 if severities & {"warning", "error"} else 0
    return 1 if "error" in severities else 0


def findings_summary(findings: list[ValidationFinding]) -> dict[str, int]:
    return {
        "errors": sum(1 for f in findings if f.severity == "error"),
        "warnings": sum(1 for f in findings if f.severity == "warning"),
    }


def validation_report(
    findings: list[ValidationFinding],
    path: Path,
    repo: Path | None,
    fail_on: str,
    exit_code: int,
) -> dict[str, Any]:
    summary = findings_summary(findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "statebind_json": str(path),
        "repo": str(repo) if repo else "",
        "fail_on": fail_on,
        "exit_code": exit_code,
        "passed": exit_code == 0,
        "summary": summary,
        "findings": [asdict(f) for f in findings],
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


def validate_json_file(
    path: Path,
    repo: Path | None,
    json_out: bool,
    fail_on: str,
    report_out: Path | None = None,
) -> int:
    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        message = f"StateBind contract not found: {path}"
        report = validation_report(
            [ValidationFinding("error", "contract_not_found", message)],
            path,
            repo,
            fail_on,
            1,
        )
        if json_out:
            print(json.dumps(report, indent=2))
        else:
            print(message, file=sys.stderr)
        if report_out:
            report_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return 1
    except json.JSONDecodeError as exc:
        message = f"Invalid StateBind JSON in {path}: {exc}"
        report = validation_report(
            [ValidationFinding("error", "invalid_json", message)],
            path,
            repo,
            fail_on,
            1,
        )
        if json_out:
            print(json.dumps(report, indent=2))
        else:
            print(message, file=sys.stderr)
        if report_out:
            report_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return 1
    resolved_repo = repo.resolve() if repo else None
    findings = validate_contract(contract, repo=resolved_repo)
    exit_code = validation_exit_code(findings, fail_on)
    report = validation_report(findings, path, resolved_repo, fail_on, exit_code)
    if json_out:
        print(json.dumps(report, indent=2))
    else:
        print(render_validation_text(findings))
    if report_out:
        report_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return exit_code


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

    p_validate = sub.add_parser("validate", help="validate statebind.json structure and executable handles")
    p_validate.add_argument("statebind_json", type=Path)
    p_validate.add_argument("--repo", type=Path, default=Path("."), help="repo root for path-handle checks")
    p_validate.add_argument("--json", action="store_true", help="print machine-readable validation findings")
    p_validate.add_argument("--report", type=Path, help="write a CI-friendly validation report JSON")
    p_validate.add_argument("--fail-on", choices=["error", "warning"], default="error")

    p_schema = sub.add_parser("schema", help="print the StateBind JSON schema")
    p_schema.add_argument("--out", type=Path, help="write schema JSON to a file")

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
    if args.cmd == "validate":
        return validate_json_file(args.statebind_json, args.repo, args.json, args.fail_on, args.report)
    if args.cmd == "schema":
        text = json.dumps(STATEBIND_SCHEMA, indent=2)
        if args.out:
            args.out.write_text(text + "\n", encoding="utf-8")
            print(f"Wrote {args.out}")
        else:
            print(text)
        return 0
    if args.cmd == "demo":
        print(write_demo())
        return 0
    raise AssertionError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main())
