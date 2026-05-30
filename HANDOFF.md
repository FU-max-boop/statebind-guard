# Agent Handoff

## Task
- Goal: Keep StateBind Guard release work executable, auditable, and CI-gated.
- Current status: repository dogfoods StateBind Guard before release

## Active Target
- Type: release
- Handle: `statebind_handoff/statebind_handoff.py`
- Evidence: primary CLI implementation for StateBind Guard
- Confidence: high

## Executable Bindings

| Role | Handle | Evidence | Confidence | Risk |
|---|---|---|---|---|
| release_gate_command | `make public-check` | Makefile public-ready gate | high | |
| package_gate_command | `make package-check` | Makefile package CLI smoke gate | high | |
| ci_workflow | `.github/workflows/smoke.yml` | repository CI workflow for unit, package, and local action smoke tests | high | |
| adoption_workflow | `.github/workflows/statebind-guard.yml` | dogfood workflow that validates this contract with the local composite action | high | |
| public_docs | `docs/index.html` | GitHub Pages product surface | high | |

## Next Action
1. Verify the branch and worktree state.
2. Run `make public-check`.
3. Publish only after local gates and GitHub Actions pass.

## Risks And Ambiguities
- Release tags must stay aligned with DEFAULT_ACTION_REF and documentation examples.

## Resume Prompt

> Before release work, read HANDOFF.md and statebind.json, verify the current branch, run make public-check, and only publish after CI passes.
