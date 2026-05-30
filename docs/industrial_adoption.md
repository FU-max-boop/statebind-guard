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
statebind validate statebind.json \
  --repo . \
  --fail-on error \
  --report statebind-validation.json \
  --sarif statebind-validation.sarif
```

For repositories that keep `statebind.json` committed, install a local
pre-commit guard:

```bash
statebind install-hook --fail-on warning
```

The hook is deliberately local. It writes `.git/hooks/pre-commit`, refuses to
overwrite an existing hook unless `--force` is passed, and validates the
machine-readable handoff before each commit.

### Level 2: CI Gate

Require handoff contracts for risky agent-generated PRs:

```yaml
- uses: FU-max-boop/statebind-guard@v0.1.2
  with:
    handoff: HANDOFF.md
    statebind-json: statebind.json
    fail-on: warning
```

Or call the CLI directly:

```bash
statebind validate statebind.json \
  --repo . \
  --fail-on warning \
  --json \
  --report statebind-validation.json \
  --sarif statebind-validation.sarif
```

Use `--fail-on warning` when the handoff must be consumption-ready, not merely
structurally valid.

Upload the SARIF report with `github/codeql-action/upload-sarif@v3` to make
StateBind findings visible in GitHub code scanning and PR annotations.

The machine contract is versioned. The current schema lives at
`schemas/statebind.schema.json` and can be printed by the CLI:

```bash
statebind schema
```

### Level 3: Agent Runtime Hook

Before an agent resumes, load `statebind.json`, verify the bound files/tests/PRs
against live repo state, and refuse to act on vague handles such as "the
previous test" or "the SHA above".

## What Makes This Industrial

- Dependency-free CLI for low-friction adoption.
- Reusable GitHub composite action for copy-paste CI adoption.
- Versioned JSON schema for agent/runtime interoperability.
- Machine-readable findings for CI and agent runtimes.
- SARIF output for GitHub-native code scanning and PR annotation workflows.
- Conservative validation: uncertain handles stay uncertain.
- Explicit claim boundary: this prevents wrong-object actions; it does not
  solve all memory, retrieval, or planning failures.

## Roadmap To 1.0

1. Collect a natural corpus of failed and successful coding-agent handoffs.
2. Add adapters for Codex, Claude Code, OpenHands, Cursor, and GitHub Actions.
3. Add benchmark slices for wrong-file, wrong-test, wrong-commit, wrong-PR, and
   stale-artifact continuation failures.
4. Expand from real-shaped failure cases to collected deployed-agent sessions.
5. Collect third-party feedback from coding-agent and CI-tooling maintainers.

Current case study:

- [schema and CI report upgrade](case_studies/schema_report_upgrade.md)
