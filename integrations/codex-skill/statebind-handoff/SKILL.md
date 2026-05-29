---
name: statebind-handoff
description: Create, audit, or consume executable handoffs for coding agents such as Codex, Claude Code, Cursor, OpenHands, and other long-running software agents. Use when ending or resuming a coding task, switching windows/models/agents, generating HANDOFF.md/statebind.json, checking whether a summary preserves active target to semantic role to executable handle bindings, or reducing wrong-file/wrong-command/wrong-PR/wrong-commit continuation errors.
---

# StateBind Handoff

## Core Idea

A coding-agent handoff is not correct just because it contains relevant context. It is correct when it preserves the executable binding needed for the next action:

```text
active target -> semantic role -> executable handle
```

Examples of executable handles: file paths, test selectors, shell commands, PR/issue URLs, commit SHAs, branch names, artifact IDs, run IDs, dataset versions, API endpoints.

## Workflow

### 1. Choose The Mode

- **Create handoff**: user is ending a long task or switching agent/window.
- **Resume handoff**: user wants Codex to continue from an existing `HANDOFF.md` or `statebind.json`.
- **Audit handoff**: user wants to know whether a summary/handoff is actionable or risky.
- **Convert notes**: user has transcript/logs and wants a cleaner handoff contract.

### 2. Gather Evidence

Use only evidence that can be inspected or verified. Prefer:

- `git status`, `git diff --name-only`, `git branch --show-current`, recent commits.
- Transcript/tool logs, terminal output, test output, issue/PR text.
- Existing `README`, task notes, benchmark reports, or previous `HANDOFF.md`.

Do not invent handles. If a handle is not verified, mark it `uncertain`.

For a quick draft from an installed skill, run:

```bash
python ~/.codex/skills/statebind-handoff/scripts/statebind_handoff.py extract \
  --repo . \
  --transcript ./transcript.md \
  --repo-label . \
  --transcript-label ./transcript.md \
  --out HANDOFF.md \
  --json statebind.json
```

Then manually verify and tighten the output.

Validate the machine-readable contract:

```bash
python ~/.codex/skills/statebind-handoff/scripts/statebind_handoff.py validate \
  statebind.json \
  --repo . \
  --fail-on error \
  --report statebind-validation.json \
  --sarif statebind-validation.sarif
```

### 3. Build The Binding Contract

For each binding, record:

```text
role: semantic purpose in the task
handle: exact executable object
evidence: where it came from
confidence: high / medium / low / uncertain
risk: ambiguity or stale-object risk
```

Good binding:

```text
role=failing_test
handle=pytest tests/test_router.py::test_stream_response
evidence=terminal output from last failing run
confidence=high
```

Bad binding:

```text
role=test
handle=the failing router test
evidence=none
confidence=unknown
```

### 4. Output Human And Machine Formats

Create both when useful:

- `HANDOFF.md`: readable by the next human/Codex session.
- `statebind.json`: machine-readable contract for future scripts or tooling.
- `statebind-validation.sarif`: optional GitHub code-scanning report for CI.

Use `references/handoff_contract.md` for the Markdown template, JSON shape, risk taxonomy, and resume prompt template.

### 5. Audit Quality

A handoff passes only if:

- Every critical next action has an exact executable handle.
- Every handle has evidence or is explicitly marked uncertain.
- Modified files, failing tests, next command, working directory, branch, and active PR/issue are either bound or marked not applicable.
- `statebind.json` passes `validate` without errors before another agent consumes it.
- `statebind-validation.json` and, for GitHub workflows, `statebind-validation.sarif`
  are available when the result needs to be uploaded or reviewed by CI.
- Ambiguous candidates are listed as risks rather than silently resolved.
- The resume prompt tells the next agent to verify freshness before editing.

Red flags:

- "the file", "the test", "the PR", "the previous command" without exact handles.
- Multiple similar files/tests/commits but no active role binding.
- Summary says what happened but not what to run or edit next.
- Handles copied from old/stale context without evidence.

### 6. Resume Safely

When resuming from a handoff, first verify:

```text
1. current working directory
2. git branch/status
3. bound files exist
4. bound test/command still makes sense
5. no newer evidence contradicts the handoff
```

If the handoff conflicts with the current repo state, pause and repair the handoff before editing.
