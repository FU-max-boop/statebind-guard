# StateBind Guard Launch Package

This page is the copy-paste package for introducing StateBind Guard to coding-agent, CI, and research-engineering audiences.

## One-Liner

StateBind Guard catches coding-agent handoffs where the right file, test, PR, SHA, or artifact is visible but not bound to the role the next agent must act on.

## Short Pitch

Coding agents increasingly resume from summaries, memory files, and traces. The brittle point is not just recall. It is executable state: knowing exactly which visible handle is the failing test, comparison base, current artifact, or next command.

StateBind Guard turns that failure mode into a small contract and CI gate:

```text
active target -> semantic role -> executable handle
```

It ships as a dependency-free Python CLI, GitHub Action, SARIF/HTML/Markdown reports, policy-as-code gates, and benchmark cards.
The current benchmark package includes a deployed-derived corpus from sanitized
release, CI, packaging, SARIF/report, Pages, skill-sync, and adoption handoffs.

## Proof Snippet

```bash
python -m pip install "git+https://github.com/FU-max-boop/statebind-guard.git@v0.1.38"
statebind proof
```

Expected shape:

```text
StateBind proof: visible handle is not executable state

bad_visible_unbound: FAIL (1 error(s), 1 warning(s))
good_role_bound: PASS (0 error(s), 0 warning(s))
```

The bad case contains the right command in evidence, but the actual handle is still "the previous test." The good case binds `failing_test` to an exact pytest selector.

## Who Should Care

- Coding-agent tool builders who need safer resume and handoff boundaries.
- CI maintainers adding guardrails around agent-generated pull requests.
- Research engineers evaluating memory, retrieval, and continuation failures.
- Teams using Codex, Claude Code, OpenHands, Cursor, or custom agent loops.

## Maintainer Pitch

> I built StateBind Guard around a small handoff failure I kept seeing in long-running coding-agent work: the next agent can see the right handle, but the role binding is gone. The tool is dependency-free, has a GitHub Action, emits SARIF/HTML/Markdown/JSON, and includes a one-command proof. I would be curious whether this matches any resume/handoff failures you have seen in your agent workflow.

## Launch Post

> I released StateBind Guard: a tiny CLI + GitHub Action for executable coding-agent handoffs.
>
> The failure mode: a handoff mentions the right file/test/SHA/PR, but loses what that handle is for.
>
> StateBind checks:
>
> `active target -> semantic role -> executable handle`
>
> Try the proof:
>
> `statebind proof`
>
> It shows a visible-but-unbound handoff failing and a role-bound handoff passing.

## Technical Claims To Defend

- Visibility is not the same as executable state.
- Role-bound handles are a small, testable contract for safer agent continuation.
- The current validator is conservative. It checks structure, vague handles, path safety, confidence, risk, and policy gates; it does not claim to solve all memory or planning failures.
- The benchmark is a scoped artifact, not a universal agent-memory benchmark.

## Adoption Path

```bash
statebind audit --repo . --markdown statebind-adoption-audit.md
statebind audit --repo . --issue-template statebind-maintainer-note.md
statebind audit --repo-url https://github.com/owner/repo --issue-template statebind-maintainer-note.md
statebind scout --repo-list candidate-repos.txt --issue-dir statebind-notes --markdown statebind-scout.md --result-card statebind-scout-card.md
statebind scout --github-list candidate-github-repos.txt --issue-context --issue-context-card statebind-issue-context.md --feedback-packet statebind-feedback-packet.md --issue-dir statebind-notes --markdown statebind-scout.md --result-card statebind-scout-card.md
statebind capture-github-run --run-url https://github.com/owner/repo/actions/runs/123 --next-command "make test" --out statebind-ci.json --handoff HANDOFF.ci.md
statebind capture-worktree --next-command "make test" --active-file src/app.py --out statebind-local.json --handoff HANDOFF.local.md
statebind proof
statebind init --goal "keep coding-agent handoffs executable" --next-command "make test" --policy-out .statebind-policy.json --pre-commit-config .pre-commit-config.yaml
statebind install-hook --policy .statebind-policy.json
statebind doctor
```

Then pin the GitHub Action:

```yaml
- uses: FU-max-boop/statebind-guard@v0.1.38
  with:
    handoff: HANDOFF.md
    statebind-json: statebind.json
    policy: .statebind-policy.json
    fail-on: warning
```

## Feedback Loop

After trying the tool, open an adoption report or sanitized failure-case issue:

- [adoption feedback guide](adoption_feedback.md)
- [roadmap](roadmap.md)
- [adoption target review](adoption_target_review_2026_05_31.md)
- [adoption context evidence](adoption_context_evidence_2026_05_31.md)
- [adoption feedback request drafts](adoption_feedback_requests_2026_05_31.md)
- [Pydantic AI maintainer feedback packet](maintainer_feedback/pydantic_ai_feedback_packet_2026_05_31.md)
- [issue templates](https://github.com/FU-max-boop/statebind-guard/issues/new/choose)
- [citation metadata](../CITATION.cff)

## Quality Receipts

- `make public-check` runs tests, schema checks, benchmark cards, smoke demo, proof, and package smoke.
- `statebind audit --repo .` gives a pre-adoption report for third-party
  repositories before asking maintainers to wire CI.
- `statebind audit --repo-url https://github.com/owner/repo` prepares the same
  report and maintainer note from a temporary shallow checkout.
- `statebind scout` ranks multiple candidate repositories before outreach and
  writes maintainer-safe notes only for non-skip targets plus compact result
  cards for human review.
- `statebind scout --github-list` uses GitHub's API to screen large repositories
  without a clone; set `GH_TOKEN` or `GITHUB_TOKEN` before larger campaigns.
- `statebind scout --issue-context-card` records current public issue context
  so feedback requests are grounded in repository-specific evidence.
- `statebind scout --issue-context-term` lets a reviewer replace generic
  defaults with target-specific terms before outreach.
- `statebind scout --feedback-packet` turns the same scout evidence into a
  human-review-gated maintainer feedback packet.
- `statebind capture-github-run` captures a real GitHub Actions runtime or run
  URL into a StateBind contract with run URL, workflow/job, conclusion,
  commit/ref, and next command.
- `statebind capture-worktree` captures local git worktree state with branch,
  head SHA, staged/modified/untracked files, active file, and next command.
- The deployed-derived result card tests sanitized release, CI, packaging,
  SARIF/report, Pages, skill-sync, and external-adoption handoffs.
- `make dist-check` builds the wheel and source distribution, checks sdist
  contents, rebuilds from the sdist, and validates the installed CLI.
- Compatibility CI runs unit tests and clean wheel package smoke on Python 3.10, 3.11, 3.12, and 3.13 across Ubuntu and macOS.
- Release-tag CI attaches verified wheel and sdist assets to the GitHub release.
- GitHub Action smoke dogfoods the local composite action on both passing and
  failing fixtures, verifying outputs and reports in each path.
- The repository and generated workflows upload SARIF through GitHub code scanning, not only as an artifact.
- Separate-repository adoption smoke passes in [statebind-guard-adoption-example](https://github.com/FU-max-boop/statebind-guard-adoption-example/actions/runs/26683277633).
- Release artifacts include JSON, SARIF, Markdown, and standalone HTML reports.
- The landing page and README link the proof, launch note, quick demo, adoption examples, pre-commit usage, policy usage, and CI usage.
