#!/usr/bin/env python3
"""Generate, check, and validate StateBind coding-agent handoffs.

This script is intentionally dependency-free. It produces a draft handoff;
Codex or a human should still verify evidence and confidence.
"""

from __future__ import annotations

import argparse
import html
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
POLICY_SCHEMA_VERSION = "0.1"
DEFAULT_ACTION_REF = "FU-max-boop/statebind-guard@v0.1.20"
CONFIDENCE_ORDER = {"uncertain": 0, "low": 1, "medium": 2, "high": 3}
SOURCE_VERSION = "0.1.20"


def resolve_package_version() -> str:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    if pyproject.exists():
        match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject.read_text(encoding="utf-8"))
        if match:
            return match.group(1)
    return SOURCE_VERSION


VERSION = resolve_package_version()
DEFAULT_POLICY: dict[str, Any] = {
    "schema_version": POLICY_SCHEMA_VERSION,
    "preset": "minimal",
    "description": "Require a verified next command before another actor consumes the handoff.",
    "required_roles": ["next_command"],
    "min_confidence": "medium",
    "require_top_level_risks": False,
}
POLICY_PRESETS: dict[str, dict[str, Any]] = {
    "minimal": DEFAULT_POLICY,
    "bugfix": {
        "schema_version": POLICY_SCHEMA_VERSION,
        "preset": "bugfix",
        "description": "Require the focused failing test and exact next command for bug-fix handoffs.",
        "required_roles": ["failing_test", "next_command"],
        "min_confidence": "medium",
        "require_top_level_risks": False,
    },
    "ci-failure": {
        "schema_version": POLICY_SCHEMA_VERSION,
        "preset": "ci-failure",
        "description": "Bind CI workflow, failing test, and next command before resuming a failed run.",
        "required_roles": ["ci_workflow", "failing_test", "next_command"],
        "min_confidence": "medium",
        "require_top_level_risks": False,
    },
    "release": {
        "schema_version": POLICY_SCHEMA_VERSION,
        "preset": "release",
        "description": "Require release gate, CI workflow, and artifact bindings with explicit risks.",
        "required_roles": ["release_gate_command", "ci_workflow", "artifact_path"],
        "min_confidence": "high",
        "require_top_level_risks": True,
    },
    "migration": {
        "schema_version": POLICY_SCHEMA_VERSION,
        "preset": "migration",
        "description": "Require target, rollback, and verification bindings for risky migrations.",
        "required_roles": ["migration_target", "rollback_command", "verification_command"],
        "min_confidence": "high",
        "require_top_level_risks": True,
    },
    "benchmark": {
        "schema_version": POLICY_SCHEMA_VERSION,
        "preset": "benchmark",
        "description": "Require dataset, benchmark command, and result artifact bindings for eval work.",
        "required_roles": ["dataset_version", "benchmark_command", "result_artifact"],
        "min_confidence": "high",
        "require_top_level_risks": True,
    },
}
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
POLICY_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://github.com/FU-max-boop/statebind-guard/schemas/statebind-policy.schema.json",
    "title": "StateBind policy",
    "type": "object",
    "required": ["schema_version"],
    "properties": {
        "schema_version": {"type": "string", "enum": [POLICY_SCHEMA_VERSION]},
        "preset": {"type": "string"},
        "description": {"type": "string"},
        "required_roles": {
            "type": "array",
            "items": {"type": "string"},
        },
        "min_confidence": {"type": "string", "enum": sorted(CONFIDENCE_VALUES)},
        "require_top_level_risks": {"type": "boolean"},
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


@dataclass
class DoctorCheck:
    status: str
    code: str
    message: str
    action: str = ""


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


def starter_contract(goal: str, next_command: str) -> dict[str, Any]:
    """Build a ready-to-validate starter contract for first-time adoption."""
    return {
        "schema_version": SCHEMA_VERSION,
        "task": {
            "goal": goal,
            "status": "ready for StateBind Guard adoption",
        },
        "active_target": {
            "type": "ci",
            "handle": next_command,
            "evidence": "statebind init starter scaffold",
            "confidence": "high",
        },
        "bindings": [
            {
                "role": "next_command",
                "handle": next_command,
                "evidence": "statebind init starter scaffold",
                "confidence": "high",
                "risk": "",
            }
        ],
        "risks": [],
        "resume_prompt": (
            "Read HANDOFF.md and statebind.json before resuming this repository. "
            "Run the bound next_command only after verifying the current branch and files."
        ),
        "raw_signals": {
            "source": "statebind init",
            "action_ref": DEFAULT_ACTION_REF,
        },
    }


def render_init_workflow(
    handoff_path: Path,
    statebind_path: Path,
    report_path: str = "statebind-validation.json",
    sarif_path: str = "statebind-validation.sarif",
) -> str:
    return f"""name: statebind-guard

on:
  pull_request:
  push:

permissions:
  contents: read
  security-events: write

jobs:
  validate-handoff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: {DEFAULT_ACTION_REF}
        with:
          handoff: {handoff_path.as_posix()}
          statebind-json: {statebind_path.as_posix()}
          fail-on: warning
          report: {report_path}
          sarif: {sarif_path}
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: statebind-validation
          path: |
            {report_path}
            {sarif_path}
            statebind-summary.md
            statebind-report.html
      - uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: {sarif_path}
"""


def write_scaffold_file(path: Path, text: str, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists; pass --force to overwrite it.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def init_scaffold(
    handoff_path: Path,
    statebind_path: Path,
    workflow_path: Path,
    goal: str,
    next_command: str,
    force: bool,
) -> list[Path]:
    contract = starter_contract(goal, next_command)
    outputs = [
        (handoff_path, render_md(contract)),
        (statebind_path, json.dumps(contract, indent=2, ensure_ascii=False) + "\n"),
        (workflow_path, render_init_workflow(handoff_path, statebind_path)),
    ]
    if not force:
        existing = [str(path) for path, _ in outputs if path.exists()]
        if existing:
            raise FileExistsError(f"{', '.join(existing)} already exists; pass --force to overwrite.")
    written: list[Path] = []
    for path, text in outputs:
        write_scaffold_file(path, text, force)
        written.append(path)
    return written


def git_hook_path(repo: Path) -> Path:
    hook = run(["git", "rev-parse", "--git-path", "hooks/pre-commit"], repo)
    if not hook:
        raise RuntimeError(f"{repo} does not look like a Git repository.")
    path = Path(hook)
    if not path.is_absolute():
        path = repo / path
    return path


def render_pre_commit_hook(statebind_path: Path, fail_on: str, policy_path: Path | None = None) -> str:
    executable = json.dumps(sys.executable)
    script = json.dumps(str(Path(__file__).resolve()))
    policy = json.dumps(policy_path.as_posix() if policy_path else "")
    return f"""#!/usr/bin/env sh
set -eu

STATEBIND_JSON={json.dumps(statebind_path.as_posix())}
STATEBIND_POLICY={policy}
STATEBIND_SCRIPT={script}
PYTHON={executable}

if [ ! -f "$STATEBIND_JSON" ]; then
  echo "StateBind Guard: $STATEBIND_JSON is missing. Run statebind init or update the hook path." >&2
  exit 1
fi

if [ -n "$STATEBIND_POLICY" ] && [ ! -f "$STATEBIND_POLICY" ]; then
  echo "StateBind Guard: $STATEBIND_POLICY is missing. Update the hook policy path." >&2
  exit 1
fi

if "$PYTHON" -c "import statebind_handoff.statebind_handoff" >/dev/null 2>&1; then
  set -- -m statebind_handoff.statebind_handoff validate "$STATEBIND_JSON" --repo . --fail-on {fail_on} --quiet
else
  set -- "$STATEBIND_SCRIPT" validate "$STATEBIND_JSON" --repo . --fail-on {fail_on} --quiet
fi

if [ -n "$STATEBIND_POLICY" ]; then
  set -- "$@" --policy "$STATEBIND_POLICY"
fi

exec "$PYTHON" "$@"
"""


def install_git_hook(repo: Path, statebind_path: Path, fail_on: str, force: bool, policy_path: Path | None = None) -> Path:
    hook = git_hook_path(repo.resolve())
    if hook.exists() and not force:
        raise FileExistsError(f"{hook} already exists; pass --force to overwrite it.")
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(render_pre_commit_hook(statebind_path, fail_on, policy_path), encoding="utf-8")
    hook.chmod(0o755)
    return hook


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
    else:
        if "goal" not in task:
            add_finding(findings, "error", "missing_task_goal", "Task `goal` is required by the schema.")
        elif is_blank(task.get("goal")):
            add_finding(findings, "warning", "blank_task_goal", "Task goal is blank; fill it before handoff consumption.")
        if "status" not in task:
            add_finding(findings, "error", "missing_task_status", "Task `status` is required by the schema.")
        elif is_blank(task.get("status")):
            add_finding(findings, "warning", "blank_task_status", "Task status is blank; fill it before handoff consumption.")

    active_target = contract.get("active_target")
    if not isinstance(active_target, dict):
        add_finding(findings, "error", "missing_active_target", "Missing `active_target` object.")
    else:
        for field in ("type", "handle", "evidence"):
            if field not in active_target:
                add_finding(
                    findings,
                    "error",
                    f"missing_active_target_{field}",
                    f"Active target `{field}` is required by the schema.",
                )
            elif is_blank(active_target.get(field)):
                add_finding(
                    findings,
                    "warning",
                    f"blank_active_target_{field}",
                    f"Active target `{field}` is blank; bind the current object before resuming.",
                )
        if "confidence" not in active_target:
            add_finding(
                findings,
                "error",
                "missing_active_target_confidence",
                "Active target `confidence` is required by the schema.",
            )
        confidence = str(active_target.get("confidence", "")).strip()
        if not confidence:
            add_finding(
                findings,
                "error",
                "blank_active_target_confidence",
                "Active target `confidence` must be one of high, medium, low, or uncertain.",
            )
        elif confidence not in CONFIDENCE_VALUES:
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

        if "role" not in raw:
            add_finding(findings, "error", "missing_binding_role", f"Binding #{idx} schema requires `role`.")
        if is_blank(role):
            add_finding(findings, "error", "blank_binding_role", f"Binding #{idx} has a blank role.")
        if "handle" not in raw:
            add_finding(findings, "error", "missing_binding_handle", f"Binding #{idx} schema requires `handle`.", role)
        if is_blank(handle):
            add_finding(findings, "error", "blank_binding_handle", f"Binding #{idx} has a blank handle.", role)
        if "evidence" not in raw:
            add_finding(findings, "error", "missing_binding_evidence", f"Binding `{role}` schema requires `evidence`.", role, handle)
        if is_blank(evidence):
            add_finding(findings, "error", "blank_binding_evidence", f"Binding `{role}` has blank evidence.", role, handle)

        if "confidence" not in raw:
            add_finding(
                findings,
                "error",
                "missing_binding_confidence",
                f"Binding `{role}` schema requires `confidence`.",
                role,
                handle,
            )
        if not confidence:
            add_finding(
                findings,
                "error",
                "blank_binding_confidence",
                f"Binding `{role}` confidence must be one of {sorted(CONFIDENCE_VALUES)}.",
                role,
                handle,
            )
        elif confidence not in CONFIDENCE_VALUES:
            add_finding(
                findings,
                "error",
                "invalid_binding_confidence",
                f"Binding `{role}` confidence `{confidence}` is not one of {sorted(CONFIDENCE_VALUES)}.",
                role,
                handle,
            )
        if "risk" not in raw:
            add_finding(findings, "error", "missing_binding_risk", f"Binding `{role}` schema requires `risk`.", role, handle)

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


def validate_policy_config(policy: Any) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    if not isinstance(policy, dict):
        return [ValidationFinding("error", "policy_not_object", "StateBind policy must be a JSON object.")]

    schema_version = str(policy.get("schema_version", "")).strip()
    if not schema_version:
        add_finding(findings, "error", "policy_missing_schema_version", "`schema_version` is required in policy.")
    elif schema_version != POLICY_SCHEMA_VERSION:
        add_finding(
            findings,
            "error",
            "policy_unsupported_schema_version",
            f"Policy schema_version {schema_version!r} is not supported; expected {POLICY_SCHEMA_VERSION!r}.",
        )

    required_roles = policy.get("required_roles", [])
    if not isinstance(required_roles, list) or not all(isinstance(role, str) and role.strip() for role in required_roles):
        add_finding(findings, "error", "policy_invalid_required_roles", "`required_roles` must be a list of non-empty strings.")

    min_confidence = policy.get("min_confidence")
    if min_confidence is not None and min_confidence not in CONFIDENCE_VALUES:
        add_finding(
            findings,
            "error",
            "policy_invalid_min_confidence",
            f"`min_confidence` must be one of {sorted(CONFIDENCE_VALUES)}.",
        )

    require_risks = policy.get("require_top_level_risks", False)
    if not isinstance(require_risks, bool):
        add_finding(
            findings,
            "error",
            "policy_invalid_require_top_level_risks",
            "`require_top_level_risks` must be true or false.",
        )

    return findings


def apply_policy(contract: dict[str, Any], policy: Any) -> list[ValidationFinding]:
    findings = validate_policy_config(policy)
    if any(f.severity == "error" for f in findings):
        return findings

    assert isinstance(policy, dict)
    bindings = contract.get("bindings")
    if not isinstance(bindings, list):
        bindings = []

    roles = {str(raw.get("role", "")).strip() for raw in bindings if isinstance(raw, dict)}
    for role in policy.get("required_roles", []):
        if role not in roles:
            add_finding(
                findings,
                "error",
                "policy_missing_required_role",
                f"Policy requires a `{role}` binding.",
                role,
            )

    min_confidence = policy.get("min_confidence")
    if min_confidence in CONFIDENCE_ORDER:
        min_rank = CONFIDENCE_ORDER[min_confidence]
        active_target = contract.get("active_target")
        if isinstance(active_target, dict):
            confidence = str(active_target.get("confidence", "")).strip()
            if confidence in CONFIDENCE_ORDER and CONFIDENCE_ORDER[confidence] < min_rank:
                add_finding(
                    findings,
                    "error",
                    "policy_active_target_confidence_below_min",
                    f"Active target confidence `{confidence}` is below policy minimum `{min_confidence}`.",
                    "active_target",
                    str(active_target.get("handle", "")).strip(),
                )

        for raw in bindings:
            if not isinstance(raw, dict):
                continue
            confidence = str(raw.get("confidence", "")).strip()
            if confidence in CONFIDENCE_ORDER and CONFIDENCE_ORDER[confidence] < min_rank:
                add_finding(
                    findings,
                    "error",
                    "policy_binding_confidence_below_min",
                    f"Binding confidence `{confidence}` is below policy minimum `{min_confidence}`.",
                    str(raw.get("role", "")).strip(),
                    str(raw.get("handle", "")).strip(),
                )

    if policy.get("require_top_level_risks") and not contract.get("risks"):
        add_finding(
            findings,
            "error",
            "policy_missing_top_level_risks",
            "Policy requires at least one top-level risk entry.",
        )

    return findings


def validate_policy_file(policy_path: Path, contract: dict[str, Any]) -> list[ValidationFinding]:
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [
            ValidationFinding(
                "error",
                "policy_not_found",
                f"StateBind policy not found: {policy_path}",
            )
        ]
    except json.JSONDecodeError as exc:
        return [
            ValidationFinding(
                "error",
                "policy_invalid_json",
                f"Invalid StateBind policy JSON in {policy_path}: {exc}",
            )
        ]
    return apply_policy(contract, policy)


def render_validation_text(findings: list[ValidationFinding]) -> str:
    if not findings:
        return "StateBind validation passed: no structural findings."
    lines = ["StateBind validation findings:"]
    for finding in findings:
        target = f" role={finding.role!r} handle={finding.handle!r}" if finding.role or finding.handle else ""
        lines.append(f"- [{finding.severity}] {finding.code}:{target} {finding.message}")
    return "\n".join(lines)


def markdown_cell(value: Any) -> str:
    return str(value).replace("\n", " ").replace("|", "\\|")


def html_escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def portable_display_path(value: Any) -> str:
    text = str(value)
    if not text:
        return ""
    path = Path(text)
    if path.is_absolute():
        return path.name
    return text


def github_command_escape(value: Any, property_value: bool = False) -> str:
    text = str(value)
    text = text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    if property_value:
        text = text.replace(":", "%3A").replace(",", "%2C")
    return text


def render_validation_markdown(report: dict[str, Any]) -> str:
    status = "PASS" if report["passed"] else "FAIL"
    summary = report["summary"]
    lines = [
        "# StateBind Guard",
        "",
        f"**Status:** {status}",
        f"**Contract:** `{report['statebind_json']}`",
        f"**Policy:** `{report['policy'] or '[none]'}`",
        f"**Fail on:** `{report['fail_on']}`",
        f"**Findings:** {summary['errors']} error(s), {summary['warnings']} warning(s)",
        "",
    ]
    findings = report["findings"]
    if not findings:
        lines.append("No structural findings.")
        lines.append("")
        return "\n".join(lines)

    lines.extend(
        [
            "| Severity | Code | Role | Handle | Message |",
            "|---|---|---|---|---|",
        ]
    )
    for finding in findings:
        lines.append(
            "| "
            + " | ".join(
                markdown_cell(finding.get(key, ""))
                for key in ("severity", "code", "role", "handle", "message")
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)


def render_github_annotations(report: dict[str, Any]) -> str:
    lines: list[str] = []
    file_path = portable_display_path(report["statebind_json"]) or "statebind.json"
    for finding in report["findings"]:
        severity = "error" if finding.get("severity") == "error" else "warning"
        title = f"StateBind {finding.get('code', 'finding')}"
        details = str(finding.get("message", ""))
        if finding.get("role"):
            details += f" role={finding['role']!r}"
        if finding.get("handle"):
            details += f" handle={finding['handle']!r}"
        lines.append(
            f"::{severity} file={github_command_escape(file_path, property_value=True)},"
            f"title={github_command_escape(title, property_value=True)}::"
            f"{github_command_escape(details)}"
        )
    return "\n".join(lines)


def write_github_output(path: Path, report: dict[str, Any]) -> None:
    summary = report["summary"]
    outputs = {
        "passed": "true" if report["passed"] else "false",
        "errors": str(summary["errors"]),
        "warnings": str(summary["warnings"]),
        "exit_code": str(report["exit_code"]),
        "fail_on": str(report["fail_on"]),
        "statebind_json": portable_display_path(report["statebind_json"]) or "statebind.json",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        for key, value in outputs.items():
            file.write(f"{key}={value}\n")


def render_validation_html(report: dict[str, Any]) -> str:
    status = "PASS" if report["passed"] else "FAIL"
    status_class = "pass" if report["passed"] else "fail"
    summary = report["summary"]
    contract = portable_display_path(report["statebind_json"])
    policy = portable_display_path(report["policy"]) if report["policy"] else "[none]"
    findings = report["findings"]
    rows = []
    for finding in findings:
        rows.append(
            "<tr>"
            f"<td><span class=\"pill {html_escape(finding.get('severity', ''))}\">{html_escape(finding.get('severity', ''))}</span></td>"
            f"<td><code>{html_escape(finding.get('code', ''))}</code></td>"
            f"<td>{html_escape(finding.get('role', ''))}</td>"
            f"<td><code>{html_escape(finding.get('handle', ''))}</code></td>"
            f"<td>{html_escape(finding.get('message', ''))}</td>"
            "</tr>"
        )
    finding_block = (
        "<p class=\"empty\">No structural or policy findings.</p>"
        if not rows
        else (
            "<table><thead><tr><th>Severity</th><th>Code</th><th>Role</th>"
            "<th>Handle</th><th>Message</th></tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table>"
        )
    )
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>StateBind Guard Report</title>
    <style>
      :root {{
        color-scheme: light;
        --ink: #151922;
        --muted: #647084;
        --line: #d8dee9;
        --surface: #ffffff;
        --paper: #f6f8fb;
        --pass: #0f766e;
        --fail: #b42318;
        --warn: #b35c00;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        background: var(--paper);
        color: var(--ink);
        font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        line-height: 1.55;
      }}
      main {{
        width: min(980px, calc(100% - 32px));
        margin: 0 auto;
        padding: 48px 0;
      }}
      .hero, .panel {{
        border: 1px solid var(--line);
        border-radius: 8px;
        background: var(--surface);
      }}
      .hero {{
        padding: 28px;
      }}
      h1 {{
        margin: 0 0 8px;
        font-size: 36px;
        line-height: 1.1;
        letter-spacing: 0;
      }}
      .meta {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 12px;
        margin-top: 24px;
      }}
      .item {{
        border: 1px solid var(--line);
        border-radius: 8px;
        padding: 14px;
      }}
      .label {{
        color: var(--muted);
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
      }}
      .value {{
        margin-top: 4px;
        overflow-wrap: anywhere;
        font-weight: 700;
      }}
      .status {{
        display: inline-flex;
        align-items: center;
        border-radius: 999px;
        padding: 5px 10px;
        color: #ffffff;
        font-size: 13px;
        font-weight: 800;
      }}
      .status.pass {{ background: var(--pass); }}
      .status.fail {{ background: var(--fail); }}
      .panel {{
        margin-top: 18px;
        padding: 22px;
      }}
      h2 {{
        margin: 0 0 14px;
        font-size: 22px;
      }}
      table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 14px;
      }}
      th, td {{
        border-top: 1px solid var(--line);
        padding: 10px 8px;
        text-align: left;
        vertical-align: top;
      }}
      th {{
        color: var(--muted);
        font-size: 12px;
        text-transform: uppercase;
      }}
      code {{
        font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      }}
      .pill {{
        border-radius: 999px;
        padding: 3px 8px;
        color: #ffffff;
        font-size: 12px;
        font-weight: 800;
      }}
      .pill.error {{ background: var(--fail); }}
      .pill.warning {{ background: var(--warn); }}
      .empty {{
        margin: 0;
        color: var(--muted);
      }}
      @media (max-width: 720px) {{
        .meta {{ grid-template-columns: 1fr; }}
        h1 {{ font-size: 30px; }}
      }}
    </style>
  </head>
  <body>
    <main>
      <section class="hero">
        <span class="status {status_class}">{status}</span>
        <h1>StateBind Guard Report</h1>
        <p>Executable handoff validation for role-bound files, commands, policy requirements, and risk gates.</p>
        <div class="meta">
          <div class="item"><div class="label">Contract</div><div class="value"><code>{html_escape(contract)}</code></div></div>
          <div class="item"><div class="label">Policy</div><div class="value"><code>{html_escape(policy)}</code></div></div>
          <div class="item"><div class="label">Fail On</div><div class="value"><code>{html_escape(report['fail_on'])}</code></div></div>
          <div class="item"><div class="label">Findings</div><div class="value">{summary['errors']} error(s), {summary['warnings']} warning(s)</div></div>
        </div>
      </section>
      <section class="panel">
        <h2>Findings</h2>
        {finding_block}
      </section>
    </main>
  </body>
</html>
"""


def write_output(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
    policy_path: Path | None = None,
) -> dict[str, Any]:
    summary = findings_summary(findings)
    return {
        "schema_version": SCHEMA_VERSION,
        "statebind_json": str(path),
        "policy": str(policy_path) if policy_path else "",
        "repo": str(repo) if repo else "",
        "fail_on": fail_on,
        "exit_code": exit_code,
        "passed": exit_code == 0,
        "summary": summary,
        "findings": [asdict(f) for f in findings],
    }


def sarif_level(severity: str) -> str:
    if severity == "error":
        return "error"
    if severity == "warning":
        return "warning"
    return "note"


def sarif_uri(path: Path, repo: Path | None) -> str:
    resolved = path.resolve()
    if repo:
        try:
            return resolved.relative_to(repo.resolve()).as_posix()
        except ValueError:
            pass
    return path.as_posix()


def sarif_report(
    findings: list[ValidationFinding],
    path: Path,
    repo: Path | None,
    fail_on: str,
    exit_code: int,
) -> dict[str, Any]:
    rules: list[dict[str, Any]] = []
    for code in sorted({finding.code for finding in findings}):
        sample = next(finding for finding in findings if finding.code == code)
        rules.append(
            {
                "id": code,
                "name": code,
                "shortDescription": {"text": code.replace("_", " ")},
                "fullDescription": {"text": sample.message},
                "help": {
                    "text": (
                        "Inspect the StateBind handoff contract and replace ambiguous "
                        "or missing executable handles with explicit role-bound values."
                    )
                },
                "properties": {
                    "problem.severity": sample.severity,
                    "tags": ["statebind", "agent-handoff", sample.severity],
                },
            }
        )

    uri = sarif_uri(path, repo)
    results: list[dict[str, Any]] = []
    for finding in findings:
        result: dict[str, Any] = {
            "ruleId": finding.code,
            "level": sarif_level(finding.severity),
            "message": {"text": finding.message},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": uri},
                    }
                }
            ],
        }
        properties = {
            k: v
            for k, v in {"role": finding.role, "handle": finding.handle}.items()
            if v
        }
        if properties:
            result["properties"] = properties
        results.append(result)

    summary = findings_summary(findings)
    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "StateBind Guard",
                        "version": SCHEMA_VERSION,
                        "informationUri": "https://github.com/FU-max-boop/statebind-guard",
                        "rules": rules,
                    }
                },
                "invocations": [
                    {
                        "executionSuccessful": exit_code == 0,
                        "properties": {
                            "fail_on": fail_on,
                            "errors": summary["errors"],
                            "warnings": summary["warnings"],
                        },
                    }
                ],
                "results": results,
            }
        ],
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
    sarif_out: Path | None = None,
    summary_out: Path | None = None,
    html_report_out: Path | None = None,
    policy_path: Path | None = None,
    github_output_out: Path | None = None,
    github_annotations: bool = False,
    quiet: bool = False,
) -> int:
    try:
        contract = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        message = f"StateBind contract not found: {path}"
        findings = [ValidationFinding("error", "contract_not_found", message)]
        report = validation_report(
            findings,
            path,
            repo,
            fail_on,
            1,
            policy_path,
        )
        if json_out:
            print(json.dumps(report, indent=2))
        else:
            print(message, file=sys.stderr)
        if report_out:
            write_output(report_out, json.dumps(report, indent=2))
        if sarif_out:
            write_output(sarif_out, json.dumps(sarif_report(findings, path, repo, fail_on, 1), indent=2))
        if summary_out:
            write_output(summary_out, render_validation_markdown(report))
        if html_report_out:
            write_output(html_report_out, render_validation_html(report))
        if github_output_out:
            write_github_output(github_output_out, report)
        if github_annotations:
            annotations = render_github_annotations(report)
            if annotations:
                print(annotations, file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        message = f"Invalid StateBind JSON in {path}: {exc}"
        findings = [ValidationFinding("error", "invalid_json", message)]
        report = validation_report(
            findings,
            path,
            repo,
            fail_on,
            1,
            policy_path,
        )
        if json_out:
            print(json.dumps(report, indent=2))
        else:
            print(message, file=sys.stderr)
        if report_out:
            write_output(report_out, json.dumps(report, indent=2))
        if sarif_out:
            write_output(sarif_out, json.dumps(sarif_report(findings, path, repo, fail_on, 1), indent=2))
        if summary_out:
            write_output(summary_out, render_validation_markdown(report))
        if html_report_out:
            write_output(html_report_out, render_validation_html(report))
        if github_output_out:
            write_github_output(github_output_out, report)
        if github_annotations:
            annotations = render_github_annotations(report)
            if annotations:
                print(annotations, file=sys.stderr)
        return 1
    resolved_repo = repo.resolve() if repo else None
    findings = validate_contract(contract, repo=resolved_repo)
    if policy_path:
        resolved_policy = resolve_repo_path(resolved_repo or Path("."), policy_path)
        findings.extend(validate_policy_file(resolved_policy, contract))
    exit_code = validation_exit_code(findings, fail_on)
    report = validation_report(findings, path, resolved_repo, fail_on, exit_code, policy_path)
    if json_out:
        print(json.dumps(report, indent=2))
    elif not quiet or findings:
        print(render_validation_text(findings))
    if report_out:
        write_output(report_out, json.dumps(report, indent=2))
    if sarif_out:
        write_output(
            sarif_out,
            json.dumps(
                sarif_report(findings, path, resolved_repo, fail_on, exit_code),
                indent=2,
            ),
        )
    if summary_out:
        write_output(summary_out, render_validation_markdown(report))
    if html_report_out:
        write_output(html_report_out, render_validation_html(report))
    if github_output_out:
        write_github_output(github_output_out, report)
    if github_annotations:
        annotations = render_github_annotations(report)
        if annotations:
            print(annotations, file=sys.stderr)
    return exit_code


def resolve_repo_path(repo: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo / path


def add_doctor_check(
    checks: list[DoctorCheck],
    status: str,
    code: str,
    message: str,
    action: str = "",
) -> None:
    checks.append(DoctorCheck(status, code, message, action))


def read_optional_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def doctor_report(
    repo: Path,
    statebind_path: Path,
    handoff_path: Path,
    workflow_path: Path,
    fail_on: str,
    policy_path: Path | None = None,
) -> dict[str, Any]:
    repo = repo.resolve()
    checks: list[DoctorCheck] = []
    validation_findings: list[ValidationFinding] = []
    contract: dict[str, Any] | None = None

    if repo.exists():
        add_doctor_check(checks, "ok", "repo", f"Repository path exists: {repo}")
    else:
        add_doctor_check(checks, "error", "repo", f"Repository path does not exist: {repo}")

    git_hook: Path | None = None
    try:
        git_hook = git_hook_path(repo)
        add_doctor_check(checks, "ok", "git_repo", "Git metadata is available.")
    except RuntimeError:
        add_doctor_check(
            checks,
            "warning",
            "git_repo",
            "Git metadata is not available; local hook checks are skipped.",
            "Run this inside a Git repository before installing the local hook.",
        )

    statebind_abs = resolve_repo_path(repo, statebind_path)
    handoff_abs = resolve_repo_path(repo, handoff_path)
    workflow_abs = resolve_repo_path(repo, workflow_path)

    if statebind_abs.exists():
        add_doctor_check(checks, "ok", "statebind_json", f"Found {statebind_path.as_posix()}.")
        try:
            contract = json.loads(statebind_abs.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            add_doctor_check(
                checks,
                "error",
                "statebind_json_parse",
                f"{statebind_path.as_posix()} is not valid JSON: {exc}",
                "Fix the JSON syntax, then rerun `statebind doctor`.",
            )
        else:
            validation_findings = validate_contract(contract, repo=repo)
            validation_exit = validation_exit_code(validation_findings, fail_on)
            summary = findings_summary(validation_findings)
            if validation_findings:
                status = "error" if validation_exit else "warning"
                add_doctor_check(
                    checks,
                    status,
                    "statebind_validation",
                    (
                        f"Validation found {summary['errors']} error(s) and "
                        f"{summary['warnings']} warning(s) with --fail-on {fail_on}."
                    ),
                    f"Run `statebind validate {statebind_path.as_posix()} --repo . --fail-on {fail_on}`.",
                )
            else:
                add_doctor_check(checks, "ok", "statebind_validation", "Contract validates with no findings.")
    else:
        add_doctor_check(
            checks,
            "error",
            "statebind_json",
            f"Missing {statebind_path.as_posix()}.",
            'Run `statebind init --goal "..." --next-command "make test"`.',
        )

    if handoff_abs.exists():
        add_doctor_check(checks, "ok", "handoff_markdown", f"Found {handoff_path.as_posix()}.")
    else:
        add_doctor_check(
            checks,
            "warning",
            "handoff_markdown",
            f"Missing {handoff_path.as_posix()}.",
            "Keep a human-readable handoff next to the machine contract.",
        )

    workflow_text = read_optional_text(workflow_abs)
    if workflow_text:
        if "statebind-guard" in workflow_text and "statebind-json" in workflow_text:
            add_doctor_check(checks, "ok", "github_action", f"Workflow references StateBind Guard: {workflow_path.as_posix()}.")
        else:
            add_doctor_check(
                checks,
                "warning",
                "github_action",
                f"Workflow exists but does not look wired to StateBind Guard: {workflow_path.as_posix()}.",
                "Use `statebind init --force` or copy the GitHub Action example from the docs.",
            )
    else:
        add_doctor_check(
            checks,
            "warning",
            "github_action",
            f"Missing GitHub Action workflow at {workflow_path.as_posix()}.",
            "Commit a workflow that uses `FU-max-boop/statebind-guard`.",
        )

    pre_commit_config = next(
        (
            path
            for path in (repo / ".pre-commit-config.yaml", repo / ".pre-commit-config.yml")
            if path.exists()
        ),
        None,
    )
    if pre_commit_config:
        config_text = read_optional_text(pre_commit_config)
        if "statebind-guard" in config_text:
            add_doctor_check(
                checks,
                "ok",
                "pre_commit_config",
                f"Standard pre-commit config includes StateBind Guard: {pre_commit_config.name}.",
            )
        else:
            add_doctor_check(
                checks,
                "warning",
                "pre_commit_config",
                f"{pre_commit_config.name} exists but does not include StateBind Guard.",
                "Add the `statebind-guard` hook from docs/pre_commit_usage.md.",
            )
    else:
        add_doctor_check(
            checks,
            "warning",
            "pre_commit_config",
            "No standard pre-commit config found.",
            "Add `.pre-commit-config.yaml` if your team uses the pre-commit framework.",
        )

    if git_hook:
        hook_text = read_optional_text(git_hook)
        if hook_text and "StateBind Guard" in hook_text and "statebind" in hook_text:
            add_doctor_check(checks, "ok", "local_git_hook", f"Local Git hook is installed: {git_hook}.")
        else:
            add_doctor_check(
                checks,
                "warning",
                "local_git_hook",
                "Local Git pre-commit hook is not installed for this checkout.",
                f"Run `statebind install-hook --repo . --json {statebind_path.as_posix()}`.",
            )
    else:
        add_doctor_check(
            checks,
            "warning",
            "local_git_hook",
            "Local Git pre-commit hook could not be checked without Git metadata.",
            "Run `git init` before installing the local hook.",
        )

    resolved_policy_path = policy_path
    if resolved_policy_path is None and (repo / ".statebind-policy.json").exists():
        resolved_policy_path = Path(".statebind-policy.json")

    if resolved_policy_path:
        policy_abs = resolve_repo_path(repo, resolved_policy_path)
        if not policy_abs.exists():
            add_doctor_check(
                checks,
                "warning",
                "policy_file",
                f"StateBind policy is configured but missing: {resolved_policy_path.as_posix()}.",
                "Run `statebind policy --out .statebind-policy.json` or update the policy path.",
            )
        else:
            if contract is not None:
                policy_findings = validate_policy_file(policy_abs, contract)
            else:
                try:
                    policy_findings = validate_policy_config(json.loads(policy_abs.read_text(encoding="utf-8")))
                except json.JSONDecodeError as exc:
                    policy_findings = [
                        ValidationFinding(
                            "error",
                            "policy_invalid_json",
                            f"Invalid StateBind policy JSON in {resolved_policy_path.as_posix()}: {exc}",
                        )
                    ]
            validation_findings.extend(policy_findings)
            if policy_findings:
                summary = findings_summary(policy_findings)
                add_doctor_check(
                    checks,
                    "error",
                    "policy_validation",
                    (
                        f"Policy found {summary['errors']} error(s) and "
                        f"{summary['warnings']} warning(s): {resolved_policy_path.as_posix()}."
                    ),
                    f"Run `statebind validate {statebind_path.as_posix()} --repo . --policy {resolved_policy_path.as_posix()}`.",
                )
            else:
                add_doctor_check(checks, "ok", "policy_file", f"Policy validates: {resolved_policy_path.as_posix()}.")

    summary = {
        "ok": sum(1 for check in checks if check.status == "ok"),
        "warnings": sum(1 for check in checks if check.status == "warning"),
        "errors": sum(1 for check in checks if check.status == "error"),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "repo": str(repo),
        "fail_on": fail_on,
        "paths": {
            "statebind_json": statebind_path.as_posix(),
            "handoff": handoff_path.as_posix(),
            "workflow": workflow_path.as_posix(),
            "policy": resolved_policy_path.as_posix() if resolved_policy_path else "",
        },
        "passed": summary["errors"] == 0,
        "summary": summary,
        "checks": [asdict(check) for check in checks],
        "validation_findings": [asdict(finding) for finding in validation_findings],
    }


def render_doctor_text(report: dict[str, Any]) -> str:
    lines = ["StateBind adoption doctor:"]
    for check in report["checks"]:
        lines.append(f"- [{check['status']}] {check['code']}: {check['message']}")
        if check.get("action"):
            lines.append(f"  next: {check['action']}")
    if report["validation_findings"]:
        lines.append("")
        lines.append(render_validation_text([ValidationFinding(**finding) for finding in report["validation_findings"]]))
    summary = report["summary"]
    lines.append("")
    lines.append(
        f"Summary: {summary['ok']} ok, {summary['warnings']} warning(s), "
        f"{summary['errors']} error(s)."
    )
    return "\n".join(lines)


def run_doctor(
    repo: Path,
    statebind_path: Path,
    handoff_path: Path,
    workflow_path: Path,
    fail_on: str,
    policy_path: Path | None,
    json_out: bool,
) -> int:
    report = doctor_report(repo, statebind_path, handoff_path, workflow_path, fail_on, policy_path)
    if json_out:
        print(json.dumps(report, indent=2))
    else:
        print(render_doctor_text(report))
    return 1 if report["summary"]["errors"] else 0


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


def proof_contracts() -> dict[str, dict[str, Any]]:
    bad = {
        "schema_version": SCHEMA_VERSION,
        "task": {
            "goal": "resume the streaming-test fix",
            "status": "ambiguous summary",
        },
        "active_target": {
            "type": "test",
            "handle": "the previous test",
            "evidence": (
                "The handoff visibly lists `pytest tests/test_router.py::test_stream_response` "
                "and `make test`, but never binds either command to the failing-test role."
            ),
            "confidence": "high",
        },
        "bindings": [
            {
                "role": "failing_test",
                "handle": "the previous test",
                "evidence": (
                    "Visible command strings include `pytest tests/test_router.py::test_stream_response` "
                    "and `make test`."
                ),
                "confidence": "high",
                "risk": "",
            }
        ],
        "risks": [],
    }
    good = {
        "schema_version": SCHEMA_VERSION,
        "task": {
            "goal": "resume the streaming-test fix",
            "status": "ready",
        },
        "active_target": {
            "type": "test",
            "handle": "pytest tests/test_router.py::test_stream_response",
            "evidence": "Latest red test after the streaming resume patch.",
            "confidence": "high",
        },
        "bindings": [
            {
                "role": "failing_test",
                "handle": "pytest tests/test_router.py::test_stream_response",
                "evidence": "Bound as the exact failing selector to run before broad tests.",
                "confidence": "high",
                "risk": "",
            },
            {
                "role": "next_command",
                "handle": "pytest tests/test_router.py::test_stream_response",
                "evidence": "Smallest safe verification command before `make test`.",
                "confidence": "high",
                "risk": "",
            },
        ],
        "risks": [],
    }
    return {"bad_visible_unbound": bad, "good_role_bound": good}


def proof_report(json_out: bool = False) -> int:
    cases: dict[str, dict[str, Any]] = {}
    for name, contract in proof_contracts().items():
        findings = validate_contract(contract)
        exit_code = validation_exit_code(findings, "warning")
        cases[name] = validation_report(findings, Path(f"{name}.json"), None, "warning", exit_code)

    if json_out:
        print(json.dumps({"schema_version": SCHEMA_VERSION, "cases": cases}, indent=2))
        return 0

    print("StateBind proof: visible handle is not executable state")
    print("")
    for label, report in cases.items():
        summary = report["summary"]
        status = "PASS" if report["passed"] else "FAIL"
        print(f"{label}: {status} ({summary['errors']} error(s), {summary['warnings']} warning(s))")
        for finding in report["findings"]:
            target = ""
            if finding.get("role") or finding.get("handle"):
                target = f" role={finding.get('role', '')!r} handle={finding.get('handle', '')!r}"
            print(f"  - [{finding['severity']}] {finding['code']}:{target} {finding['message']}")
        if not report["findings"]:
            print("  - no structural or policy findings")
    print("")
    print("Takeaway: the bad handoff shows the command in evidence, but the executable handle is vague.")
    print("The good handoff binds the failing-test role to the exact pytest selector.")
    return 0


def policy_text(preset: str) -> str:
    return json.dumps(POLICY_PRESETS[preset], indent=2) + "\n"


def render_policy_presets() -> str:
    lines = ["StateBind policy presets:"]
    for name in sorted(POLICY_PRESETS):
        policy = POLICY_PRESETS[name]
        roles = ", ".join(policy["required_roles"])
        lines.append(
            f"- {name}: min_confidence={policy['min_confidence']}, "
            f"require_top_level_risks={str(policy['require_top_level_risks']).lower()}, "
            f"roles=[{roles}]"
        )
        lines.append(f"  {policy['description']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="StateBind handoff helper")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_extract = sub.add_parser("extract", help="generate HANDOFF.md/statebind.json draft")
    p_extract.add_argument("--repo", type=Path, default=Path("."))
    p_extract.add_argument("--transcript", type=Path)
    p_extract.add_argument("--out", type=Path, default=Path("HANDOFF.md"))
    p_extract.add_argument("--json", type=Path, default=Path("statebind.json"))
    p_extract.add_argument("--repo-label", help="portable label to write instead of an absolute repo path")
    p_extract.add_argument("--transcript-label", help="portable label to write instead of an absolute transcript path")

    p_init = sub.add_parser("init", help="create a ready-to-run handoff contract and GitHub workflow")
    p_init.add_argument("--handoff", type=Path, default=Path("HANDOFF.md"))
    p_init.add_argument("--json", type=Path, default=Path("statebind.json"))
    p_init.add_argument("--workflow", type=Path, default=Path(".github/workflows/statebind-guard.yml"))
    p_init.add_argument(
        "--goal",
        default="Preserve executable coding-agent handoff bindings for this repository.",
    )
    p_init.add_argument("--next-command", default="make test")
    p_init.add_argument("--force", action="store_true", help="overwrite existing scaffold files")

    p_install_hook = sub.add_parser("install-hook", help="install a local Git pre-commit StateBind guard")
    p_install_hook.add_argument("--repo", type=Path, default=Path("."))
    p_install_hook.add_argument("--json", type=Path, default=Path("statebind.json"))
    p_install_hook.add_argument("--policy", type=Path, help="apply a StateBind policy in the local hook")
    p_install_hook.add_argument("--fail-on", choices=["error", "warning"], default="warning")
    p_install_hook.add_argument("--force", action="store_true", help="overwrite an existing pre-commit hook")

    p_doctor = sub.add_parser("doctor", help="audit StateBind Guard adoption for this repository")
    p_doctor.add_argument("--repo", type=Path, default=Path("."))
    p_doctor.add_argument("--statebind-json", type=Path, default=Path("statebind.json"))
    p_doctor.add_argument("--handoff", type=Path, default=Path("HANDOFF.md"))
    p_doctor.add_argument("--workflow", type=Path, default=Path(".github/workflows/statebind-guard.yml"))
    p_doctor.add_argument("--policy", type=Path, help="check a StateBind policy file")
    p_doctor.add_argument("--fail-on", choices=["error", "warning"], default="warning")
    p_doctor.add_argument("--json", action="store_true", help="print machine-readable adoption diagnostics")

    p_check = sub.add_parser("check", help="basic handoff audit")
    p_check.add_argument("handoff", type=Path)

    p_validate = sub.add_parser("validate", help="validate statebind.json structure and executable handles")
    p_validate.add_argument("statebind_json", type=Path)
    p_validate.add_argument("--repo", type=Path, default=Path("."), help="repo root for path-handle checks")
    p_validate.add_argument("--json", action="store_true", help="print machine-readable validation findings")
    p_validate.add_argument("--report", type=Path, help="write a CI-friendly validation report JSON")
    p_validate.add_argument("--sarif", type=Path, help="write GitHub code-scanning compatible SARIF")
    p_validate.add_argument("--summary", type=Path, help="write a Markdown validation summary")
    p_validate.add_argument("--html-report", type=Path, help="write a standalone HTML validation report")
    p_validate.add_argument("--policy", type=Path, help="apply a StateBind policy JSON file")
    p_validate.add_argument("--github-output", type=Path, help="append GitHub Actions step outputs to this file")
    p_validate.add_argument("--github-annotations", action="store_true", help="emit GitHub Actions workflow annotations to stderr")
    p_validate.add_argument("--fail-on", choices=["error", "warning"], default="error")
    p_validate.add_argument("--quiet", action="store_true", help="suppress success output in text mode")

    p_policy = sub.add_parser("policy", help="print or write a starter StateBind policy")
    p_policy.add_argument("--preset", choices=sorted(POLICY_PRESETS), default="minimal", help="scenario policy preset to emit")
    p_policy.add_argument("--list-presets", action="store_true", help="list available scenario policy presets")
    p_policy.add_argument("--out", type=Path, help="write starter policy JSON to a file")
    p_policy.add_argument("--force", action="store_true", help="overwrite an existing policy file")

    p_schema = sub.add_parser("schema", help="print the StateBind JSON schema")
    p_schema.add_argument("--out", type=Path, help="write schema JSON to a file")
    p_schema.add_argument("--policy", action="store_true", help="print the StateBind policy schema")

    sub.add_parser("demo", help="print visible-but-unbound demo")
    p_proof = sub.add_parser("proof", help="run a self-contained bad-vs-good StateBind validation proof")
    p_proof.add_argument("--json", action="store_true", help="print machine-readable proof reports")

    args = parser.parse_args()
    if args.cmd == "extract":
        repo = args.repo.resolve()
        contract = to_contract(collect(repo, args.transcript, args.repo_label, args.transcript_label))
        args.out.write_text(render_md(contract), encoding="utf-8")
        args.json.write_text(json.dumps(contract, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote {args.out} and {args.json}")
        print("Draft only: verify evidence and remove stale/uncertain candidates before resuming.")
        return 0
    if args.cmd == "init":
        try:
            written = init_scaffold(args.handoff, args.json, args.workflow, args.goal, args.next_command, args.force)
        except FileExistsError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        for path in written:
            print(f"Wrote {path}")
        print("Next: commit these files and let the StateBind Guard workflow validate future handoffs.")
        return 0
    if args.cmd == "install-hook":
        try:
            hook = install_git_hook(args.repo, args.json, args.fail_on, args.force, args.policy)
        except (FileExistsError, RuntimeError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(f"Wrote {hook}")
        print(f"StateBind Guard pre-commit hook will validate {args.json} with --fail-on {args.fail_on}.")
        if args.policy:
            print(f"StateBind Guard pre-commit hook will apply policy {args.policy}.")
        return 0
    if args.cmd == "doctor":
        return run_doctor(
            args.repo,
            args.statebind_json,
            args.handoff,
            args.workflow,
            args.fail_on,
            args.policy,
            args.json,
        )
    if args.cmd == "check":
        return check_handoff(args.handoff)
    if args.cmd == "validate":
        return validate_json_file(
            args.statebind_json,
            args.repo,
            args.json,
            args.fail_on,
            args.report,
            args.sarif,
            args.summary,
            args.html_report,
            args.policy,
            args.github_output,
            args.github_annotations,
            args.quiet,
        )
    if args.cmd == "policy":
        if args.list_presets:
            print(render_policy_presets())
            return 0
        text = policy_text(args.preset)
        if args.out:
            try:
                write_scaffold_file(args.out, text, args.force)
            except FileExistsError as exc:
                print(str(exc), file=sys.stderr)
                return 2
            print(f"Wrote {args.out}")
        else:
            print(text, end="")
        return 0
    if args.cmd == "schema":
        text = json.dumps(POLICY_SCHEMA if args.policy else STATEBIND_SCHEMA, indent=2)
        if args.out:
            args.out.write_text(text + "\n", encoding="utf-8")
            print(f"Wrote {args.out}")
        else:
            print(text)
        return 0
    if args.cmd == "demo":
        print(write_demo())
        return 0
    if args.cmd == "proof":
        return proof_report(args.json)
    raise AssertionError(args.cmd)


if __name__ == "__main__":
    raise SystemExit(main())
