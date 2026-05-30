# Visible Context Is Not Executable State

Coding agents are getting good at resuming from summaries, memory files,
retrieval snippets, and tool traces. The weak point is no longer whether the
next agent can see the right identifier. The weak point is whether the next
agent knows what that identifier is for.

StateBind Guard is built around a narrow claim:

```text
visible handle != role-bound executable state
```

A handoff can mention the right file, test, PR, SHA, branch, or artifact and
still be unsafe if it does not preserve the binding from:

```text
active target -> semantic role -> executable handle
```

## The Failure Mode

Suppose a handoff mentions three SHAs:

```text
head SHA: abc1234
base SHA: def5678
stale SHA: 999aaaa
```

A resumed agent that reads "use the SHA above" has visible context, but not an
executable binding. It can easily use the head SHA where the comparison-base
SHA was required.

The same pattern appears in coding work:

```text
two test commands visible -> only one is the current failing test
three files visible -> only one is the active patch target
two artifacts visible -> only one is the latest valid output
```

These are not retrieval failures in the simple sense. They are binding
failures.

## What StateBind Adds

StateBind asks handoffs to preserve five small fields for action-relevant
objects:

| Field | Purpose |
|---|---|
| `role` | What is this handle for? |
| `handle` | What exact object should be used? |
| `evidence` | Why is this binding trustworthy? |
| `confidence` | How strong is the binding? |
| `risk` | What ambiguity remains? |

That turns an ambiguous handoff:

```text
Continue from the PR and use the SHA above.
```

into an executable one:

```text
comparison_base_sha -> def5678
evidence -> PR metadata row base.sha
risk -> do not use head SHA abc1234
```

## What Ships

StateBind Guard is intentionally small and dependency-free:

- `statebind init` creates `HANDOFF.md`, `statebind.json`, and a GitHub workflow.
- `statebind validate` checks structure, vague handles, path safety, and missing executable bindings.
- `statebind doctor` audits whether the repository has the contract, handoff, CI, and local hooks wired.
- JSON, SARIF, and Markdown summary outputs make the result usable in CI,
  GitHub code scanning, and human review.
- A composite GitHub Action lets repositories adopt the guard in one workflow step.
- Benchmark and failure-corpus cards document the included visible-but-unbound cases.

## Try It

```bash
python -m pip install "git+https://github.com/FU-max-boop/statebind-guard.git@v0.1.5"
statebind init --goal "keep coding-agent handoffs executable" --next-command "make test"
statebind install-hook
statebind doctor
git add HANDOFF.md statebind.json .github/workflows/statebind-guard.yml
```

Then use the generated workflow or call the action directly:

```yaml
- uses: FU-max-boop/statebind-guard@v0.1.5
  with:
    handoff: HANDOFF.md
    statebind-json: statebind.json
    fail-on: warning
```

## Boundary Of The Claim

StateBind Guard does not claim that retrieval, summaries, or memory files are
bad. It claims that visibility is an insufficient quality gate for resumed
agent work. If the next action depends on a file, test, PR, SHA, branch,
artifact, or command, the handoff should preserve the role-bound executable
handle.

That is the smallest safety contract for long-running coding agents:

```text
not just what was seen, but what should be acted on
```
