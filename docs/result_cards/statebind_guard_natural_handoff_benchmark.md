# StateBind Guard Natural Handoff Benchmark

## Hypothesis

Merely preserving visible IDs, paths, commands, URLs, or SHAs is not enough
for safe coding-agent handoff. A role-to-handle binding check should reduce
unsafe acceptance of handoffs that mention the right handle but do not bind it
to the active role.

## Decision Gate

Promote StateBind Guard as the first practical artifact only if it beats a
visibility baseline and a keyword-role baseline while reducing unsafe accepts
on failing handoffs.

## Results

| Method | Accuracy | Unsafe accept rate | Accept F1 | TP | TN | FP | FN |
|---|---:|---:|---:|---:|---:|---:|---:|
| visibility_baseline | 0.500 | 1.000 | 0.667 | 8 | 0 | 8 | 0 |
| keyword_role_baseline | 0.500 | 1.000 | 0.667 | 8 | 0 | 8 | 0 |
| statebind_guard | 1.000 | 0.000 | 1.000 | 8 | 8 | 0 | 0 |

## Category Coverage

| Category | Records | Pass | Fail |
|---|---:|---:|---:|
| uncategorized | 16 | 8 | 8 |

## Verdict

StateBind Guard beats both baselines on this benchmark.

## Scope

This benchmark contains 16 anonymized, real-shaped
handoff snippets. It is designed to test the visible-but-unbound failure
mode, not to claim broad deployed-agent coverage.

## Next Upgrade

Collect natural handoffs from real Codex/Claude/OpenHands sessions and keep
the same gate: fewer unsafe accepts than naive visibility and keyword baselines.
