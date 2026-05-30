# Policy Usage

StateBind policies let a team turn a handoff convention into a repeatable
CI gate. The policy is intentionally small JSON so it can be reviewed like any
other quality rule.

Create a starter policy:

```bash
statebind policy --out .statebind-policy.json
```

List scenario presets:

```bash
statebind policy --list-presets
```

Generate a stricter preset:

```bash
statebind policy --preset release --out .statebind-policy.json --force
```

Presets:

| Preset | Use case | Required roles |
|---|---|---|
| `minimal` | first adoption | `next_command` |
| `bugfix` | focused bug fix | `failing_test`, `next_command` |
| `ci-failure` | failed workflow continuation | `ci_workflow`, `failing_test`, `next_command` |
| `release` | package or artifact release | `release_gate_command`, `ci_workflow`, `artifact_path` |
| `migration` | risky migration | `migration_target`, `rollback_command`, `verification_command` |
| `benchmark` | eval or benchmark run | `dataset_version`, `benchmark_command`, `result_artifact` |

Example release policy:

```json
{
  "schema_version": "0.1",
  "preset": "release",
  "description": "Require release gate, CI workflow, and artifact bindings with explicit risks.",
  "required_roles": ["release_gate_command", "ci_workflow", "artifact_path"],
  "min_confidence": "high",
  "require_top_level_risks": true
}
```

Validate with the policy:

```bash
statebind validate statebind.json \
  --repo . \
  --policy .statebind-policy.json \
  --fail-on warning \
  --report statebind-validation.json \
  --sarif statebind-validation.sarif \
  --summary statebind-summary.md \
  --html-report statebind-report.html
```

The policy currently supports:

- `required_roles`: every listed role must appear in `bindings`.
- `min_confidence`: active target and bindings must meet the confidence floor.
- `require_top_level_risks`: `risks` must contain at least one explicit entry.

Use policy gates for repositories where agent handoffs are consumed by another
person, model, CI job, or release process. Keep the required roles concrete:
`next_command`, `failing_test`, `release_gate_command`, `ci_workflow`, and
`artifact_path` are useful because they point to executable next actions.
