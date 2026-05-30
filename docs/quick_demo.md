# StateBind Guard Quick Demo

StateBind Guard tests a narrow but costly handoff failure:

> The next agent can see the right handle, but the handoff does not bind it to
> the role that makes it executable.

## One Command

```bash
statebind proof
```

Expected shape:

```text
bad_visible_unbound: FAIL
good_role_bound: PASS
```

The bad handoff includes the right command in evidence, but the executable
handle is still vague. The good handoff binds the `failing_test` role to the
exact pytest selector.

## Benchmark Command

```bash
make benchmark
```

## Adoption Audit

Before wiring CI in a third-party repository, run:

```bash
statebind audit --repo . --markdown statebind-adoption-audit.md
```

The audit finds existing handoff-like files, checks whether StateBind is already
wired, infers the smallest likely local verification command, and prints a
copy-paste first adoption PR.

## Current Results

| Benchmark | Method | Accuracy | Unsafe accept rate |
|---|---|---:|---:|
| Seed | visibility baseline | 0.500 | 1.000 |
| Seed | keyword-role baseline | 0.750 | 0.500 |
| Seed | StateBind Guard | 1.000 | 0.000 |
| Natural handoff | visibility baseline | 0.500 | 1.000 |
| Natural handoff | keyword-role baseline | 0.500 | 1.000 |
| Natural handoff | StateBind Guard | 1.000 | 0.000 |
| Failure corpus | visibility baseline | 0.500 | 1.000 |
| Failure corpus | keyword-role baseline | 0.605 | 0.789 |
| Failure corpus | StateBind Guard | 1.000 | 0.000 |
| Deployed corpus | visibility baseline | 0.500 | 1.000 |
| Deployed corpus | keyword-role baseline | 0.500 | 1.000 |
| Deployed corpus | StateBind Guard | 1.000 | 0.000 |

The failure corpus covers wrong-file, wrong-test, wrong-commit, wrong-PR,
stale-artifact, config/environment, dataset-version, run-ID, branch-name,
risky-command, and multi-binding handoff failures.

The deployed corpus adds sanitized handoffs from real StateBind Guard release,
CI, packaging, SARIF/report, Pages, skill-sync, and external adoption workflows.

## Example Failure

This looks informative but is unsafe:

```text
The failing test is in the resume area.

Observed command strings:
- pytest tests/test_agent_resume.py::test_restore_state
- pytest tests/test_cli.py
- make test

Next action: rerun the test after patching.
```

The target test is visible, but not bound to the `failing_test` role. A resume
agent could run the wrong command while still appearing to use the context.

## Example Pass

```text
failing_test -> pytest tests/test_agent_resume.py::test_restore_state
evidence: latest red test after the memory patch

Next action: rerun that selector before any broader test suite.
```

The role and handle are bound in the same executable statement.

## Design Boundary

This benchmark does not claim to solve all agent memory failures. It targets a
specific safety layer: rejecting handoffs where an executable handle is merely
visible rather than role-bound.
