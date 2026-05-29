# Contributing

StateBind Guard welcomes small, evidence-backed contributions. The project is
about preserving executable state in coding-agent handoffs, so changes should
keep the claim narrow and testable.

## Good Contributions

- New handoff failure cases with exact role/handle/evidence fields.
- Better validators for vague or stale executable handles.
- CI/runtime adapters for coding-agent workflows.
- Benchmark slices that distinguish visibility from binding.
- Documentation that makes the boundary of the claim clearer.

## Quality Bar

Before opening a PR, run:

```bash
make test
make benchmark
make public-check
```

For validator changes, include at least one positive and one negative test.

## Claim Boundary

Do not frame StateBind as a complete solution to agent memory, RAG, planning,
or software-engineering reliability. The core invariant is narrower:

```text
active target -> semantic role -> executable handle
```

If a change broadens the claim, add a limitation or benchmark evidence that
supports the broader statement.
