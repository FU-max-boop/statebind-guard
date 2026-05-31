# Adoption Audit

`statebind audit` is the pre-adoption command for maintainers who want to know
whether StateBind Guard fits their repository before wiring CI.

Run it from a repository root:

```bash
statebind audit --repo . --markdown statebind-adoption-audit.md
```

Or evaluate a public Git repository without manually cloning it:

```bash
statebind audit --repo-url https://github.com/owner/repo \
  --issue-template statebind-maintainer-note.md
```

`--repo-url` uses a temporary shallow Git checkout. The generated maintainer
note uses the repository name and relative paths, not the local temporary
checkout path. Use `--clone-timeout 60` if the target host is slow.

## Batch Scout

Use `statebind scout` before external outreach. It ranks candidate repositories
so you can avoid low-signal or irrelevant maintainer pings:

```bash
statebind scout \
  --repo-list candidate-repos.txt \
  --issue-dir statebind-notes \
  --markdown statebind-scout.md \
  --result-card statebind-scout-card.md
```

For large GitHub repositories, avoid clone cost and use the GitHub API scout:

```bash
statebind scout \
  --github-list candidate-github-repos.txt \
  --issue-dir statebind-notes \
  --markdown statebind-scout.md \
  --result-card statebind-scout-card.md
```

Set `GH_TOKEN` or `GITHUB_TOKEN` before larger campaigns to avoid
unauthenticated GitHub API rate limits.

The scout report labels each repository as `high`, `medium`, `low`,
`follow_up`, or `skip`. Prefer `high` and `medium` targets where the audit
finds handoff-like files and a concrete local gate.
The result card is shorter: it summarizes scope, priority mix, top review
targets, and the claim boundary for human-reviewed outreach.

It scans for:

- existing `statebind.json`, `HANDOFF.md`, policy files, and StateBind workflows
- handoff-like files such as `AGENTS.md`, `AI_HANDOFF.md`, or files with
  `handoff` in the path
- the smallest likely local test/smoke command from `Makefile`, `package.json`,
  or Python project metadata

The report is intentionally maintainer-friendly. It gives an adoption level,
existing signals, handoff candidates, and the smallest copy-paste adoption PR.

For outreach or a maintainer discussion, also generate a low-pressure issue/PR
note:

```bash
statebind audit --repo . \
  --markdown statebind-adoption-audit.md \
  --issue-template statebind-maintainer-note.md
```

The issue template deliberately asks a narrow review question instead of
assuming adoption: whether the repository has a real resume or handoff boundary
where visible handles can lose their executable role binding.
It includes maintainer questions so the first reply can be "docs-only",
"CI warning", "required gate", or "not relevant" instead of a vague adoption
debate. If the repository already appears wired, the note switches from a first
adoption PR to a smallest follow-up check.

## JSON Mode

Use JSON for automation or issue bots:

```bash
statebind audit --repo . --json
```

The output includes:

- `adoption_level`: `not_started`, `partial`, or `wired`
- `handoff_candidates`: handoff-like files discovered in the repository
- `statebind_workflows`: workflows already wired to StateBind Guard
- `suggested_next_command`: the smallest inferred verification command
- `recommended_commands`: copy-paste commands for the first adoption PR

## Smallest Adoption PR

A typical first PR is deliberately small:

```bash
statebind init --goal "Preserve executable coding-agent handoffs" --next-command "make test"
statebind policy --preset bugfix --out .statebind-policy.json
statebind doctor --repo . --policy .statebind-policy.json
```

Before opening a PR, replace the inferred `--next-command` with the repository's
smallest reliable local gate.

## Privacy Boundary

Do not publish raw transcripts, local machine paths, proprietary code,
customer data, or secrets. The audit report is designed to point at public
handoff surfaces and a copy-paste adoption path, not to expose private traces.
