#!/usr/bin/env python3
"""Generate, check, and validate StateBind coding-agent handoffs.

This script is intentionally dependency-free. It produces a draft handoff;
Codex or a human should still verify evidence and confidence.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


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
AUDIT_EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    "build",
    "dist",
}
HANDOFF_NAME_HINTS = {
    "handoff.md",
    "agent_handoff.md",
    "agent-handoff.md",
    "ai_handoff.md",
    "ai-handoff.md",
    "agents.md",
    "claude.md",
    "codex.md",
}
SCHEMA_VERSION = "0.1"
POLICY_SCHEMA_VERSION = "0.1"
DEFAULT_ACTION_REF = "FU-max-boop/statebind-guard@v0.1.30"
CONFIDENCE_ORDER = {"uncertain": 0, "low": 1, "medium": 2, "high": 3}
SOURCE_VERSION = "0.1.30"


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


def iter_repo_files(repo: Path, limit: int = 4000) -> Iterable[Path]:
    seen = 0
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in AUDIT_EXCLUDED_DIRS]
        root_path = Path(root)
        for file_name in files:
            if file_name.endswith((".pyc", ".pyo", ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".tar.gz")):
                continue
            yield root_path / file_name
            seen += 1
            if seen >= limit:
                return


def repo_rel(repo: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def find_handoff_candidates(repo: Path) -> list[dict[str, str]]:
    return handoff_candidates_from_paths(repo_rel(repo, path) for path in iter_repo_files(repo))


def handoff_candidates_from_paths(paths: Iterable[str]) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for rel in paths:
        name = Path(rel).name.lower()
        rel_lower = rel.lower()
        if Path(rel).suffix.lower() not in {"", ".md", ".markdown", ".txt"}:
            continue
        if name in HANDOFF_NAME_HINTS or "handoff" in rel_lower or rel_lower.endswith("/agents.md"):
            candidates.append(
                {
                    "path": rel,
                    "reason": "handoff-like filename" if "handoff" in rel_lower else "agent instruction file",
                }
            )
        if len(candidates) >= 20:
            break
    return candidates


def infer_next_command_from_snapshot(paths: Iterable[str], texts: dict[str, str]) -> dict[str, str]:
    path_set = set(paths)
    for name in ("Makefile", "makefile"):
        if name in path_set:
            text = texts.get(name, "")
            for target, command in (
                ("public-check", "make public-check"),
                ("test", "make test"),
                ("smoke", "make smoke"),
            ):
                if re.search(rf"(?m)^{re.escape(target)}\s*:", text):
                    return {"command": command, "evidence": f"{name} target `{target}`"}

    if "package.json" in path_set:
        try:
            package = json.loads(texts.get("package.json", "{}"))
        except json.JSONDecodeError:
            package = {}
        scripts = package.get("scripts") if isinstance(package, dict) else {}
        if isinstance(scripts, dict) and "test" in scripts:
            lock_command = "pnpm test" if "pnpm-lock.yaml" in path_set else "npm test"
            return {"command": lock_command, "evidence": "package.json test script"}

    if "pyproject.toml" in path_set:
        return {"command": "python -m pytest", "evidence": "pyproject.toml present"}

    return {"command": "make test", "evidence": "default starter command; verify before committing"}


def infer_next_command(repo: Path) -> dict[str, str]:
    makefile = next((repo / name for name in ("Makefile", "makefile") if (repo / name).exists()), None)
    if makefile:
        text = read_optional_text(makefile)
        for target, command in (
            ("public-check", "make public-check"),
            ("test", "make test"),
            ("smoke", "make smoke"),
        ):
            if re.search(rf"(?m)^{re.escape(target)}\s*:", text):
                return {"command": command, "evidence": f"{makefile.name} target `{target}`"}

    package_json = repo / "package.json"
    if package_json.exists():
        try:
            package = json.loads(package_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            package = {}
        scripts = package.get("scripts") if isinstance(package, dict) else {}
        if isinstance(scripts, dict) and "test" in scripts:
            lock_command = "pnpm test" if (repo / "pnpm-lock.yaml").exists() else "npm test"
            return {"command": lock_command, "evidence": "package.json test script"}

    pyproject = repo / "pyproject.toml"
    if pyproject.exists():
        return {"command": "python -m pytest", "evidence": "pyproject.toml present"}

    return {"command": "make test", "evidence": "default starter command; verify before committing"}


def statebind_workflow_paths(repo: Path) -> list[str]:
    workflow_dir = repo / ".github" / "workflows"
    if not workflow_dir.exists():
        return []
    paths: list[str] = []
    for path in sorted(workflow_dir.glob("*.y*ml")):
        text = read_optional_text(path)
        if "statebind-guard" in text or "statebind-json" in text:
            paths.append(repo_rel(repo, path))
    return paths


def statebind_workflows_from_snapshot(paths: Iterable[str], texts: dict[str, str]) -> list[str]:
    workflow_paths: list[str] = []
    for path in sorted(paths):
        if not path.startswith(".github/workflows/"):
            continue
        if not path.endswith((".yml", ".yaml")):
            continue
        text = texts.get(path, "")
        if "statebind-guard" in text or "statebind-json" in text:
            workflow_paths.append(path)
    return workflow_paths


def repo_label_from_url(repo_url: str) -> str:
    clean = repo_url.rstrip("/")
    if clean.endswith(".git"):
        clean = clean[:-4]
    name = clean.rsplit("/", 1)[-1]
    return name or "repository"


def clone_repo_for_audit(repo_url: str, ref: str | None, target: Path, timeout: int) -> Path:
    clone_dir = target / "repo"
    cmd = ["git", "clone", "--quiet", "--depth", "1"]
    if ref:
        cmd.extend(["--branch", ref])
    cmd.extend([repo_url, str(clone_dir)])
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"git clone timed out after {timeout} seconds") from exc
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "git clone failed"
        raise RuntimeError(detail)
    return clone_dir


def add_audit_signal_checks(
    checks: list[DoctorCheck],
    statebind_exists: bool,
    statebind_label: str,
    handoff_exists: bool,
    handoff_label: str,
    candidates: list[dict[str, str]],
    workflows: list[str],
    workflow_exists: bool,
    workflow_label: str,
    policy_exists: bool,
    policy_label: str,
    suggested: dict[str, str],
) -> None:
    if statebind_exists:
        add_doctor_check(checks, "ok", "statebind_json", f"Found {statebind_label}.")
    else:
        add_doctor_check(
            checks,
            "warning",
            "statebind_json",
            f"Missing {statebind_label}.",
            f'Run `statebind init --goal "Preserve executable coding-agent handoffs" --next-command "{suggested["command"]}"`.',
        )

    if handoff_exists:
        add_doctor_check(checks, "ok", "handoff_markdown", f"Found {handoff_label}.")
    elif candidates:
        preview = ", ".join(candidate["path"] for candidate in candidates[:5])
        add_doctor_check(
            checks,
            "warning",
            "handoff_candidates",
            f"Found handoff-like files but no canonical {handoff_label}: {preview}.",
            "Bind the active file/test/command into StateBind JSON before handoff consumption.",
        )
    else:
        add_doctor_check(
            checks,
            "warning",
            "handoff_markdown",
            "No handoff-like Markdown file found.",
            "Start with `statebind init` when a coding-agent task needs to be resumed.",
        )

    if workflows:
        add_doctor_check(checks, "ok", "github_action", f"StateBind workflow present: {', '.join(workflows)}.")
    elif workflow_exists:
        add_doctor_check(
            checks,
            "warning",
            "github_action",
            f"Workflow exists but is not wired to StateBind Guard: {workflow_label}.",
            "Copy the workflow generated by `statebind init` or use the GitHub Action example.",
        )
    else:
        add_doctor_check(
            checks,
            "warning",
            "github_action",
            f"No StateBind workflow found at {workflow_label}.",
            "Add the generated workflow in the first adoption PR.",
        )

    if policy_exists:
        add_doctor_check(checks, "ok", "policy_file", f"Found {policy_label}.")
    else:
        add_doctor_check(
            checks,
            "warning",
            "policy_file",
            "No StateBind policy file found.",
            "Run `statebind policy --preset bugfix --out .statebind-policy.json` for team-specific gates.",
        )

    if suggested["evidence"].startswith("default"):
        add_doctor_check(
            checks,
            "warning",
            "suggested_next_command",
            f"Using fallback next command `{suggested['command']}`.",
            "Replace it with the repository's smallest reliable test or smoke command.",
        )
    else:
        add_doctor_check(
            checks,
            "ok",
            "suggested_next_command",
            f"Suggested next command `{suggested['command']}` from {suggested['evidence']}.",
        )


def build_audit_report(
    repo_name: str,
    statebind_exists: bool,
    handoff_exists: bool,
    workflow_exists: bool,
    policy_exists: bool,
    statebind_label: str,
    handoff_label: str,
    workflow_label: str,
    policy_label: str,
    candidates: list[dict[str, str]],
    workflows: list[str],
    suggested: dict[str, str],
) -> dict[str, Any]:
    checks: list[DoctorCheck] = []
    add_audit_signal_checks(
        checks,
        statebind_exists,
        statebind_label,
        handoff_exists,
        handoff_label,
        candidates,
        workflows,
        workflow_exists,
        workflow_label,
        policy_exists,
        policy_label,
        suggested,
    )
    if statebind_exists and workflows:
        adoption_level = "wired"
    elif statebind_exists or workflows or handoff_exists or candidates:
        adoption_level = "partial"
    else:
        adoption_level = "not_started"

    summary = {
        "ok": sum(1 for check in checks if check.status == "ok"),
        "warnings": sum(1 for check in checks if check.status == "warning"),
        "errors": sum(1 for check in checks if check.status == "error"),
    }
    recommended_commands = [
        (
            'statebind init --goal "Preserve executable coding-agent handoffs" '
            f'--next-command "{suggested["command"]}"'
        ),
        "statebind policy --preset bugfix --out .statebind-policy.json",
        "statebind doctor --repo . --policy .statebind-policy.json",
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "repo": repo_name,
        "adoption_level": adoption_level,
        "summary": summary,
        "checks": [asdict(check) for check in checks],
        "handoff_candidates": candidates,
        "statebind_workflows": workflows,
        "suggested_next_command": suggested,
        "recommended_commands": recommended_commands,
    }


def audit_report(
    repo: Path,
    statebind_path: Path,
    handoff_path: Path,
    workflow_path: Path,
    policy_path: Path | None,
    repo_label: str | None = None,
) -> dict[str, Any]:
    repo = repo.resolve()
    if not repo.exists():
        checks: list[DoctorCheck] = []
        add_doctor_check(checks, "error", "repo", f"Repository path does not exist: {repo}")
        summary = {"ok": 0, "warnings": 0, "errors": 1}
        return {
            "schema_version": SCHEMA_VERSION,
            "repo": str(repo),
            "adoption_level": "unavailable",
            "summary": summary,
            "checks": [asdict(check) for check in checks],
            "handoff_candidates": [],
            "statebind_workflows": [],
            "suggested_next_command": infer_next_command(Path(".")),
            "recommended_commands": [],
        }

    statebind_abs = resolve_repo_path(repo, statebind_path)
    handoff_abs = resolve_repo_path(repo, handoff_path)
    workflow_abs = resolve_repo_path(repo, workflow_path)
    resolved_policy = policy_path
    if resolved_policy is None and (repo / ".statebind-policy.json").exists():
        resolved_policy = Path(".statebind-policy.json")
    policy_abs = resolve_repo_path(repo, resolved_policy) if resolved_policy else None

    candidates = find_handoff_candidates(repo)
    workflows = statebind_workflow_paths(repo)
    suggested = infer_next_command(repo)
    return build_audit_report(
        repo_label or repo.name,
        statebind_abs.exists(),
        handoff_abs.exists(),
        workflow_abs.exists(),
        bool(policy_abs and policy_abs.exists()),
        statebind_path.as_posix(),
        handoff_path.as_posix(),
        workflow_path.as_posix(),
        resolved_policy.as_posix() if resolved_policy else ".statebind-policy.json",
        candidates,
        workflows,
        suggested,
    )


def render_audit_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# StateBind Adoption Audit",
        "",
        f"**Adoption level:** `{report['adoption_level']}`",
        f"**Repository:** `{report['repo']}`",
        "",
        "## Signals",
        "",
    ]
    for check in report["checks"]:
        lines.append(f"- **{check['status']} / {check['code']}**: {check['message']}")
        if check.get("action"):
            lines.append(f"  - Next: {check['action']}")
    lines.extend(["", "## Handoff Candidates", ""])
    candidates = report["handoff_candidates"]
    if candidates:
        for candidate in candidates:
            lines.append(f"- `{candidate['path']}` ({candidate['reason']})")
    else:
        lines.append("- None detected.")
    lines.extend(
        [
            "",
            "## Smallest Adoption PR",
            "",
            "```bash",
            *report["recommended_commands"],
            "```",
            "",
            "## Review Gate",
            "",
            "- Confirm the suggested next command is the smallest reliable local gate.",
            "- Replace vague handoff phrases such as `the previous test` with exact role-bound handles.",
            "- Do not include private traces, customer data, secrets, or local machine paths in public reports.",
            "",
        ]
    )
    return "\n".join(lines)


def render_audit_issue_template(report: dict[str, Any]) -> str:
    suggested = report["suggested_next_command"]
    if report["adoption_level"] == "wired":
        command_heading = "### Smallest follow-up check"
        commands = "\n".join(
            [
                "statebind doctor --repo . --policy .statebind-policy.json",
                "statebind validate statebind.json --repo . --policy .statebind-policy.json --fail-on warning",
            ]
        )
        command_note = (
            "This repository already appears wired. I would treat the next step "
            "as a follow-up check, not a first adoption PR."
        )
    else:
        command_heading = "### Smallest possible adoption PR"
        commands = "\n".join(report["recommended_commands"])
        command_note = (
            "I would not recommend adopting this automatically. The useful maintainer review "
            "question is narrower: is there a real resume/handoff boundary here where a "
            "future agent could see the right file, test, PR, SHA, or artifact but lose the "
            "role binding that makes it executable?"
        )
    candidates = report["handoff_candidates"]
    candidate_text = "\n".join(
        f"- `{candidate['path']}` ({candidate['reason']})" for candidate in candidates[:8]
    ) or "- None detected."
    warning_checks = [check for check in report["checks"] if check["status"] == "warning"]
    warning_text = "\n".join(
        f"- `{check['code']}`: {check['message']}" for check in warning_checks
    ) or "- No adoption warnings detected."
    return f"""## StateBind Guard pre-adoption audit

I ran a lightweight StateBind Guard adoption audit against this repository to
check whether executable coding-agent handoffs could be made safer without a
large workflow change.

This is not a request to adopt a dependency blindly. The goal is to give
maintainers a small, concrete review surface.

**Repository:** `{report['repo']}`
**Adoption level:** `{report['adoption_level']}`
**Suggested smallest local gate:** `{suggested['command']}` ({suggested['evidence']})

### What the audit found

{warning_text}

### Handoff-like surfaces

{candidate_text}

{command_heading}

```bash
{commands}
```

{command_note}

### Maintainer questions

- Is this failure mode relevant to this repository's coding-agent, review, or CI workflow?
- If yes, should the first step be docs-only, a CI warning, or a required gate?
- If no, I am happy to close this and leave the audit output as context.

Privacy boundary: this audit does not require posting private traces, secrets,
customer data, local paths, or proprietary code.
"""


def run_audit(
    repo: Path,
    repo_url: str | None,
    ref: str | None,
    clone_timeout: int,
    statebind_path: Path,
    handoff_path: Path,
    workflow_path: Path,
    policy_path: Path | None,
    json_out: bool,
    markdown_out: Path | None,
    issue_template_out: Path | None,
) -> int:
    repo_label = None
    tmp_ctx: tempfile.TemporaryDirectory[str] | None = None
    try:
        if repo_url:
            repo_label = repo_label_from_url(repo_url)
            tmp_ctx = tempfile.TemporaryDirectory(prefix="statebind-audit-")
            repo = clone_repo_for_audit(repo_url, ref, Path(tmp_ctx.name), clone_timeout)
        report = audit_report(repo, statebind_path, handoff_path, workflow_path, policy_path, repo_label)
        markdown = render_audit_markdown(report)
        issue_template = render_audit_issue_template(report)
        if markdown_out:
            write_output(markdown_out, markdown)
        if issue_template_out:
            write_output(issue_template_out, issue_template)
        if json_out:
            print(json.dumps(report, indent=2))
        else:
            print(markdown)
        return 1 if report["summary"]["errors"] else 0
    except RuntimeError as exc:
        print(f"StateBind audit failed: {exc}", file=sys.stderr)
        return 2
    finally:
        if tmp_ctx:
            tmp_ctx.cleanup()


def parse_github_repo(value: str) -> tuple[str, str]:
    if value.startswith(("http://", "https://")):
        parsed = urlparse(value)
        parts = [part for part in parsed.path.strip("/").split("/") if part]
    elif value.startswith("git@github.com:"):
        parts = value.split(":", 1)[1].strip("/").split("/")
    else:
        parts = value.strip("/").split("/")
    if len(parts) < 2:
        raise RuntimeError(f"GitHub repository must look like owner/repo: {value}")
    owner, repo = parts[0], parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]
    return owner, repo


def github_api_json(url: str, timeout: int) -> dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "statebind-guard",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, headers=headers)
    try:
        with urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        if exc.code == 403 and "rate limit" in detail.lower():
            detail = (
                f"{detail} Set GH_TOKEN or GITHUB_TOKEN to use authenticated "
                "GitHub API requests for larger scout campaigns."
            )
        raise RuntimeError(f"GitHub API error {exc.code} for {url}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"GitHub API request failed for {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise RuntimeError(f"GitHub API request timed out after {timeout} seconds") from exc


def github_content_text(owner: str, repo: str, path: str, ref: str, timeout: int) -> str:
    encoded_path = quote(path)
    encoded_ref = quote(ref, safe="")
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{encoded_path}?ref={encoded_ref}"
    payload = github_api_json(url, timeout)
    if payload.get("encoding") == "base64" and isinstance(payload.get("content"), str):
        return base64.b64decode(payload["content"]).decode("utf-8", errors="replace")
    return ""


def github_snapshot(owner_repo: str, ref: str | None, timeout: int) -> tuple[str, list[str], dict[str, str]]:
    owner, repo = parse_github_repo(owner_repo)
    repo_payload = github_api_json(f"https://api.github.com/repos/{owner}/{repo}", timeout)
    selected_ref = ref or repo_payload.get("default_branch") or "main"
    branch_payload = github_api_json(
        f"https://api.github.com/repos/{owner}/{repo}/branches/{quote(selected_ref, safe='')}",
        timeout,
    )
    tree_sha = branch_payload["commit"]["commit"]["tree"]["sha"]
    tree_payload = github_api_json(
        f"https://api.github.com/repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1",
        timeout,
    )
    paths = [
        item["path"]
        for item in tree_payload.get("tree", [])
        if item.get("type") == "blob" and isinstance(item.get("path"), str)
    ]
    fetch_paths = {
        "Makefile",
        "makefile",
        "package.json",
        "pyproject.toml",
    }
    fetch_paths.update(
        path
        for path in paths
        if path.startswith(".github/workflows/") and path.endswith((".yml", ".yaml"))
    )
    texts: dict[str, str] = {}
    for path in sorted(fetch_paths):
        if path in paths:
            try:
                texts[path] = github_content_text(owner, repo, path, selected_ref, timeout)
            except RuntimeError:
                texts[path] = ""
    return repo, paths, texts


def audit_github_report(
    owner_repo: str,
    ref: str | None,
    timeout: int,
    statebind_path: Path,
    handoff_path: Path,
    workflow_path: Path,
    policy_path: Path | None,
) -> dict[str, Any]:
    repo_name, paths, texts = github_snapshot(owner_repo, ref, timeout)
    path_set = set(paths)
    resolved_policy = policy_path.as_posix() if policy_path else ".statebind-policy.json"
    candidates = handoff_candidates_from_paths(paths)
    workflows = statebind_workflows_from_snapshot(paths, texts)
    suggested = infer_next_command_from_snapshot(paths, texts)
    return build_audit_report(
        repo_name,
        statebind_path.as_posix() in path_set,
        handoff_path.as_posix() in path_set,
        workflow_path.as_posix() in path_set,
        resolved_policy in path_set,
        statebind_path.as_posix(),
        handoff_path.as_posix(),
        workflow_path.as_posix(),
        resolved_policy,
        candidates,
        workflows,
        suggested,
    )


def scout_source_label(repo_url: str) -> str:
    if repo_url.startswith(("http://", "https://", "git@", "ssh://")):
        return repo_url
    return repo_label_from_url(repo_url)


def scout_score(report: dict[str, Any]) -> tuple[int, str, list[str]]:
    if report["summary"]["errors"]:
        return 0, "skip", ["audit produced errors"]
    adoption = report["adoption_level"]
    candidate_count = len(report["handoff_candidates"])
    suggested = report["suggested_next_command"]
    score = 0
    reasons: list[str] = []

    if adoption == "partial":
        score += 6
        reasons.append("handoff surfaces exist but StateBind is not fully wired")
    elif adoption == "not_started":
        score += 2
        reasons.append("no StateBind wiring detected")
    elif adoption == "wired":
        score += 1
        reasons.append("already wired; useful only for follow-up checks")

    if candidate_count:
        score += min(candidate_count, 4)
        reasons.append(f"{candidate_count} handoff-like file(s) found")
    elif adoption == "not_started":
        reasons.append("no handoff-like files found")

    if suggested["evidence"].startswith("default"):
        score -= 1
        reasons.append("verification command needs maintainer confirmation")
    else:
        score += 2
        reasons.append(f"small local gate inferred from {suggested['evidence']}")

    if candidate_count == 0 and adoption == "not_started":
        return max(score, 0), "skip", reasons
    if adoption == "wired":
        return max(score, 0), "follow_up", reasons
    if score >= 8:
        return score, "high", reasons
    if score >= 5:
        return score, "medium", reasons
    return max(score, 0), "low", reasons


def safe_issue_filename(label: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", label).strip("-._")
    return f"{name or 'repository'}-statebind-note.md"


def load_scout_urls(repo_urls: list[str], repo_list: Path | None) -> list[str]:
    urls = list(repo_urls)
    if repo_list:
        for line in repo_list.read_text(encoding="utf-8").splitlines():
            item = line.strip()
            if item and not item.startswith("#"):
                urls.append(item)
    return urls


def scout_record_from_report(
    repo_url: str,
    report: dict[str, Any],
    issue_dir: Path | None,
) -> dict[str, Any]:
    score, priority, reasons = scout_score(report)
    record = {
        "source": scout_source_label(repo_url),
        "repo": report["repo"],
        "status": "ok",
        "priority": priority,
        "score": score,
        "reasons": reasons,
        "adoption_level": report["adoption_level"],
        "candidate_count": len(report["handoff_candidates"]),
        "handoff_candidates": report["handoff_candidates"][:8],
        "suggested_next_command": report["suggested_next_command"],
        "summary": report["summary"],
        "issue_template": "",
    }
    if issue_dir and priority != "skip":
        issue_path = issue_dir / safe_issue_filename(report["repo"])
        write_output(issue_path, render_audit_issue_template(report))
        record["issue_template"] = issue_path.name
    return record


def render_scout_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# StateBind Adoption Scout",
        "",
        f"Scanned repositories: {payload['summary']['total']}",
        f"Successful audits: {payload['summary']['ok']}",
        f"Failed audits: {payload['summary']['errors']}",
        "",
        "| Priority | Score | Repository | Adoption | Candidates | Suggested gate | Note |",
        "|---|---:|---|---|---:|---|---|",
    ]
    for record in payload["repositories"]:
        gate = record.get("suggested_next_command", {}).get("command", "")
        note = record.get("issue_template") or ""
        lines.append(
            "| {priority} | {score} | `{repo}` | {adoption} | {candidates} | `{gate}` | {note} |".format(
                priority=record["priority"],
                score=record["score"],
                repo=record["repo"],
                adoption=record.get("adoption_level", ""),
                candidates=record.get("candidate_count", 0),
                gate=gate,
                note=note,
            )
        )
    lines.extend(["", "## Review Gate", ""])
    lines.append("- Prefer `high` or `medium` targets with handoff-like files and a concrete local gate.")
    lines.append("- Skip repositories with no handoff-like surface unless a maintainer explicitly asks.")
    lines.append("- Use generated notes as drafts; adapt or close if the failure mode is not relevant.")
    lines.append("")
    for record in payload["repositories"]:
        lines.extend([f"## {record['repo']}", ""])
        if record["status"] != "ok":
            lines.append(f"- status: `{record['status']}`")
            lines.append(f"- error: {record.get('error', '')}")
            lines.append("")
            continue
        lines.append(f"- priority: `{record['priority']}`")
        lines.append(f"- source: `{record['source']}`")
        for reason in record["reasons"]:
            lines.append(f"- reason: {reason}")
        if record["handoff_candidates"]:
            lines.append("- handoff candidates:")
            for candidate in record["handoff_candidates"]:
                lines.append(f"  - `{candidate['path']}` ({candidate['reason']})")
        lines.append("")
    return "\n".join(lines)


def render_scout_result_card(payload: dict[str, Any]) -> str:
    records = payload["repositories"]
    ok_records = [record for record in records if record["status"] == "ok"]
    counts = {name: 0 for name in ("high", "medium", "low", "follow_up", "skip")}
    for record in records:
        counts[record["priority"]] = counts.get(record["priority"], 0) + 1
    note_count = sum(1 for record in records if record.get("issue_template"))
    top_records = [
        record
        for record in ok_records
        if record["priority"] in {"high", "medium", "follow_up"}
    ][:8]

    lines = [
        "# StateBind Scout Result Card",
        "",
        "## Scope",
        "",
        f"- repositories scanned: {payload['summary']['total']}",
        f"- successful audits: {payload['summary']['ok']}",
        f"- failed audits: {payload['summary']['errors']}",
        f"- generated maintainer-note drafts: {note_count}",
        "",
        "## Priority Mix",
        "",
        "| Priority | Count |",
        "|---|---:|",
    ]
    for priority in ("high", "medium", "low", "follow_up", "skip"):
        lines.append(f"| `{priority}` | {counts.get(priority, 0)} |")

    lines.extend(
        [
            "",
            "## Top Review Targets",
            "",
            "| Repository | Priority | Score | Candidates | Suggested gate | Why now |",
            "|---|---|---:|---:|---|---|",
        ]
    )
    for record in top_records:
        gate = record.get("suggested_next_command", {}).get("command", "")
        why = "; ".join(record.get("reasons", [])[:2])
        lines.append(
            "| `{repo}` | `{priority}` | {score} | {candidates} | `{gate}` | {why} |".format(
                repo=markdown_cell(record["repo"]),
                priority=record["priority"],
                score=record["score"],
                candidates=record.get("candidate_count", 0),
                gate=markdown_cell(gate),
                why=markdown_cell(why),
            )
        )

    lines.extend(
        [
            "",
            "## Review Gate",
            "",
            "- Treat this card as a triage artifact, not as permission to spam maintainers.",
            "- Prefer high or medium targets with handoff-like files and an inferred local gate.",
            "- Read the repository context before opening an issue or PR.",
            "- Convert generated notes into human-reviewed, maintainer-specific feedback.",
            "",
            "## Claim Boundary",
            "",
            "This card proves the scout can find plausible adoption surfaces. It does not prove that a maintainer wants StateBind, that a repository has a real handoff failure, or that outreach should be opened without project-specific review.",
        ]
    )
    return "\n".join(lines)


def run_scout(
    repo_urls: list[str],
    repo_list: Path | None,
    github_repos: list[str],
    github_list: Path | None,
    ref: str | None,
    clone_timeout: int,
    github_timeout: int,
    statebind_path: Path,
    handoff_path: Path,
    workflow_path: Path,
    policy_path: Path | None,
    json_out: bool,
    markdown_out: Path | None,
    result_card_out: Path | None,
    issue_dir: Path | None,
) -> int:
    urls = load_scout_urls(repo_urls, repo_list)
    github_specs = load_scout_urls(github_repos, github_list)
    if not urls and not github_specs:
        print(
            "StateBind scout needs at least one --repo-url, --repo-list, --github-repo, or --github-list entry.",
            file=sys.stderr,
        )
        return 2

    records: list[dict[str, Any]] = []
    for repo_url in urls:
        tmp_ctx: tempfile.TemporaryDirectory[str] | None = None
        try:
            label = repo_label_from_url(repo_url)
            tmp_ctx = tempfile.TemporaryDirectory(prefix="statebind-scout-")
            repo = clone_repo_for_audit(repo_url, ref, Path(tmp_ctx.name), clone_timeout)
            report = audit_report(repo, statebind_path, handoff_path, workflow_path, policy_path, label)
            records.append(scout_record_from_report(repo_url, report, issue_dir))
        except RuntimeError as exc:
            records.append(
                {
                    "source": scout_source_label(repo_url),
                    "repo": repo_label_from_url(repo_url),
                    "status": "error",
                    "priority": "skip",
                    "score": 0,
                    "reasons": ["clone or audit failed"],
                    "error": str(exc),
                }
            )
        finally:
            if tmp_ctx:
                tmp_ctx.cleanup()

    for github_repo in github_specs:
        try:
            report = audit_github_report(
                github_repo,
                ref,
                github_timeout,
                statebind_path,
                handoff_path,
                workflow_path,
                policy_path,
            )
            records.append(scout_record_from_report(github_repo, report, issue_dir))
        except RuntimeError as exc:
            records.append(
                {
                    "source": github_repo,
                    "repo": repo_label_from_url(github_repo),
                    "status": "error",
                    "priority": "skip",
                    "score": 0,
                    "reasons": ["GitHub API scout failed"],
                    "error": str(exc),
                }
            )

    records.sort(key=lambda item: (item["status"] == "ok", item["score"]), reverse=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "summary": {
            "total": len(records),
            "ok": sum(1 for record in records if record["status"] == "ok"),
            "errors": sum(1 for record in records if record["status"] != "ok"),
        },
        "repositories": records,
    }
    markdown = render_scout_markdown(payload)
    if markdown_out:
        write_output(markdown_out, markdown)
    if result_card_out:
        write_output(result_card_out, render_scout_result_card(payload))
    if json_out:
        print(json.dumps(payload, indent=2))
    else:
        print(markdown)
    return 0 if payload["summary"]["ok"] else 2


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

    p_audit = sub.add_parser("audit", help="pre-adoption scan for the smallest StateBind Guard PR")
    p_audit.add_argument("--repo", type=Path, default=Path("."))
    p_audit.add_argument("--repo-url", help="clone and audit a public Git repository without a manual checkout")
    p_audit.add_argument("--ref", help="branch or tag to clone when using --repo-url")
    p_audit.add_argument("--clone-timeout", type=int, default=30, help="seconds before a --repo-url clone fails")
    p_audit.add_argument("--statebind-json", type=Path, default=Path("statebind.json"))
    p_audit.add_argument("--handoff", type=Path, default=Path("HANDOFF.md"))
    p_audit.add_argument("--workflow", type=Path, default=Path(".github/workflows/statebind-guard.yml"))
    p_audit.add_argument("--policy", type=Path, help="check a StateBind policy file")
    p_audit.add_argument("--json", action="store_true", help="print machine-readable adoption audit")
    p_audit.add_argument("--markdown", type=Path, help="write a maintainer-friendly Markdown audit")
    p_audit.add_argument("--issue-template", type=Path, help="write a maintainer-safe GitHub issue/PR note")

    p_scout = sub.add_parser("scout", help="rank repositories for careful StateBind adoption outreach")
    p_scout.add_argument("--repo-url", action="append", default=[], help="Git repository URL or local Git path to scout")
    p_scout.add_argument("--repo-list", type=Path, help="newline-delimited repository URLs to scout")
    p_scout.add_argument("--github-repo", action="append", default=[], help="GitHub owner/repo to scout through the GitHub API")
    p_scout.add_argument("--github-list", type=Path, help="newline-delimited GitHub owner/repo entries to scout through the GitHub API")
    p_scout.add_argument("--ref", help="branch or tag to clone for each repository")
    p_scout.add_argument("--clone-timeout", type=int, default=30, help="seconds before a scout clone fails")
    p_scout.add_argument("--github-timeout", type=int, default=20, help="seconds before a GitHub API scout request fails")
    p_scout.add_argument("--statebind-json", type=Path, default=Path("statebind.json"))
    p_scout.add_argument("--handoff", type=Path, default=Path("HANDOFF.md"))
    p_scout.add_argument("--workflow", type=Path, default=Path(".github/workflows/statebind-guard.yml"))
    p_scout.add_argument("--policy", type=Path, help="check a StateBind policy file")
    p_scout.add_argument("--json", action="store_true", help="print machine-readable scout ranking")
    p_scout.add_argument("--markdown", type=Path, help="write a Markdown scout report")
    p_scout.add_argument("--result-card", type=Path, help="write a compact scout result card")
    p_scout.add_argument("--issue-dir", type=Path, help="write one maintainer-safe note per successful audit")

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
    if args.cmd == "audit":
        return run_audit(
            args.repo,
            args.repo_url,
            args.ref,
            args.clone_timeout,
            args.statebind_json,
            args.handoff,
            args.workflow,
            args.policy,
            args.json,
            args.markdown,
            args.issue_template,
        )
    if args.cmd == "scout":
        return run_scout(
            args.repo_url,
            args.repo_list,
            args.github_repo,
            args.github_list,
            args.ref,
            args.clone_timeout,
            args.github_timeout,
            args.statebind_json,
            args.handoff,
            args.workflow,
            args.policy,
            args.json,
            args.markdown,
            args.result_card,
            args.issue_dir,
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
