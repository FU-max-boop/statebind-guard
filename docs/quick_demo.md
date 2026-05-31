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

For third-party feedback prep, skip the manual clone:

```bash
statebind audit --repo-url https://github.com/owner/repo --issue-template statebind-maintainer-note.md
```

Use `statebind scout --repo-list candidate-repos.txt --issue-dir statebind-notes`
when comparing several candidate repositories before outreach.
Use `--github-list` for large GitHub repositories where cloning is too slow.
Use `--result-card statebind-scout-card.md` when the output needs to be reviewed
or shared as a compact campaign receipt.
Use `--issue-context --issue-context-card statebind-issue-context.md` to make
the scout search current public GitHub issues for handoff/resume context before
you draft maintainer-facing feedback.
Use `--issue-context-term "message history"` when the default terms are too
generic for the repository you are reviewing.
Use `--feedback-packet statebind-feedback-packet.md` to generate a
human-review-gated maintainer feedback packet from the same scout evidence.

When a GitHub Actions run fails, capture the exact runtime state:

```bash
statebind capture-github-run \
  --goal "resume failed CI" \
  --next-command "make test" \
  --out statebind-ci.json \
  --handoff HANDOFF.ci.md \
  --report statebind-validation.json
```

The captured contract binds the run URL, workflow/job, commit SHA, ref, and
next command so a later debugging actor can resume from executable state rather
than a screenshot or vague run number.

Outside the workflow, capture the same state from a run URL:

```bash
statebind capture-github-run \
  --run-url https://github.com/owner/repo/actions/runs/123 \
  --next-command "make test" \
  --out statebind-ci.json \
  --handoff HANDOFF.ci.md
```

Before handing off a dirty local worktree, capture the local executable state:

```bash
statebind capture-worktree \
  --goal "resume parser patch" \
  --next-command "python -m pytest tests/test_parser.py" \
  --active-file src/parser.py \
  --out statebind-local.json \
  --handoff HANDOFF.local.md
```

That snapshot binds the branch, head SHA, staged/modified/untracked files, the
active file, and the exact next command without writing absolute local paths.

Use `--issue-template statebind-maintainer-note.md` when preparing an external
feedback request; the note frames adoption as a maintainer question, not an
automatic recommendation.

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
