# Industrial Adoption Path

StateBind Guard is currently a public alpha. The target is a small, reliable
guardrail that coding-agent teams can place at handoff and resume boundaries.

## Production Use Case

Use StateBind when a long-running coding agent hands work to another agent,
model, terminal, CI job, or human reviewer.

The production invariant is:

```text
the next actor must know the active target, semantic role, and exact executable handle before editing or running commands
```

Examples:

- active PR -> comparison-base role -> exact base SHA
- failing CI job -> focused-test role -> exact pytest selector
- release task -> artifact role -> exact package path and checksum
- migration task -> do-not-touch role -> exact customer or dataset boundary

## Integration Levels

### Level 0: Human Checklist

Use the Markdown contract from `docs/handoff_contract.md` before ending a long
coding session.

### Level 1: Local CLI

Install the package and generate a draft:

```bash
python -m pip install -e .
statebind extract --repo . --transcript transcript.md --out HANDOFF.md --json statebind.json
statebind validate statebind.json --repo . --fail-on error
```

### Level 2: CI Gate

Require handoff contracts for risky agent-generated PRs:

```bash
statebind validate statebind.json --repo . --fail-on warning --json
```

Use `--fail-on warning` when the handoff must be consumption-ready, not merely
structurally valid.

### Level 3: Agent Runtime Hook

Before an agent resumes, load `statebind.json`, verify the bound files/tests/PRs
against live repo state, and refuse to act on vague handles such as "the
previous test" or "the SHA above".

## What Makes This Industrial

- Dependency-free CLI for low-friction adoption.
- Machine-readable findings for CI and agent runtimes.
- Conservative validation: uncertain handles stay uncertain.
- Explicit claim boundary: this prevents wrong-object actions; it does not
  solve all memory, retrieval, or planning failures.

## Roadmap To 1.0

1. Collect a natural corpus of failed and successful coding-agent handoffs.
2. Add adapters for Codex, Claude Code, OpenHands, Cursor, and GitHub Actions.
3. Publish a stable JSON schema and compatibility tests.
4. Add benchmark slices for wrong-file, wrong-test, wrong-commit, wrong-PR, and
   stale-artifact continuation failures.
5. Document real-world case studies with before/after handoff contracts.
