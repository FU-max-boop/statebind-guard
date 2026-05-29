# StateBind Guard Failure Corpus Benchmark

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
| visibility_baseline | 0.500 | 1.000 | 0.667 | 19 | 0 | 19 | 0 |
| keyword_role_baseline | 0.605 | 0.789 | 0.717 | 19 | 4 | 15 | 0 |
| statebind_guard | 1.000 | 0.000 | 1.000 | 19 | 19 | 0 | 0 |

## Category Coverage

| Category | Records | Pass | Fail |
|---|---:|---:|---:|
| branch_name | 2 | 1 | 1 |
| config_env | 4 | 2 | 2 |
| dataset_version | 2 | 1 | 1 |
| multi_binding | 4 | 2 | 2 |
| risky_command | 4 | 2 | 2 |
| run_id | 2 | 1 | 1 |
| stale_artifact | 4 | 2 | 2 |
| wrong_commit | 4 | 2 | 2 |
| wrong_file | 4 | 2 | 2 |
| wrong_pr | 4 | 2 | 2 |
| wrong_test | 4 | 2 | 2 |

## Verdict

StateBind Guard beats both baselines on this benchmark.

## Scope

This benchmark contains 38 anonymized, real-shaped
handoff snippets. It is designed to test the visible-but-unbound failure
mode, not to claim broad deployed-agent coverage.

## Next Upgrade

Collect natural handoffs from real Codex/Claude/OpenHands sessions and keep
the same gate: fewer unsafe accepts than naive visibility and keyword baselines.
