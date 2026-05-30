# StateBind Guard Deployed Corpus Benchmark

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
| visibility_baseline | 0.500 | 1.000 | 0.667 | 13 | 0 | 13 | 0 |
| keyword_role_baseline | 0.500 | 1.000 | 0.667 | 13 | 0 | 13 | 0 |
| statebind_guard | 1.000 | 0.000 | 1.000 | 13 | 13 | 0 | 0 |

## Category Coverage

| Category | Records | Pass | Fail |
|---|---:|---:|---:|
| external_adoption | 2 | 1 | 1 |
| packaging_compatibility | 2 | 1 | 1 |
| public_surface | 2 | 1 | 1 |
| release_artifact | 4 | 2 | 2 |
| release_gate | 4 | 2 | 2 |
| release_version | 2 | 1 | 1 |
| runtime_adapter | 2 | 1 | 1 |
| schema_contract | 2 | 1 | 1 |
| validation_report | 4 | 2 | 2 |
| workflow_run | 2 | 1 | 1 |

## Verdict

StateBind Guard beats both baselines on this benchmark.

## Scope

This benchmark contains 26 sanitized, deployed-derived
handoff snippets from real StateBind Guard release, CI, action,
packaging, documentation, and adoption workflows. It preserves the
role/handle structure while removing private local paths and secrets.

## Next Upgrade

Collect natural handoffs from real Codex/Claude/OpenHands sessions and keep
the same gate: fewer unsafe accepts than naive visibility and keyword baselines.
