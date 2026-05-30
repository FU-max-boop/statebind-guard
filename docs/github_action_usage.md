# GitHub Action Usage

Use the published composite action as a smoke gate when a repository stores
coding-agent handoffs such as `HANDOFF.md`, `AGENT_HANDOFF.md`, or
`docs/handoff.md`.

```yaml
name: statebind-guard

on:
  pull_request:
  push:

permissions:
  contents: read
  security-events: write

jobs:
  statebind-guard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - id: statebind
        uses: FU-max-boop/statebind-guard@v0.1.13
        with:
          handoff: HANDOFF.md
          statebind-json: statebind.json
          policy: .statebind-policy.json
          fail-on: warning
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: statebind-validation
          path: |
            statebind-validation.json
            statebind-validation.sarif
            statebind-summary.md
            statebind-report.html
      - uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: statebind-validation.sarif
```

Pin to a release tag in production, for example
`FU-max-boop/statebind-guard@v0.1.13`.

After copying the workflow, run a local adoption audit:

```bash
statebind doctor --repo .
```

The doctor confirms the workflow points at StateBind Guard and that
`statebind.json` still validates under the selected failure threshold.

The action also writes `statebind-summary.md` and appends it to the GitHub
Actions step summary. Maintainers can see pass/fail status, threshold, and
findings without opening raw logs.

It also writes `statebind-report.html`, a standalone report that can be uploaded
as a CI artifact for reviewers who want a readable validation page.

The action exposes machine-readable outputs for downstream workflow logic:

```yaml
- id: statebind
  uses: FU-max-boop/statebind-guard@v0.1.13
  with:
    statebind-json: statebind.json
    fail-on: warning
- name: Route failed handoff evidence
  if: always() && steps.statebind.outputs.passed != 'true'
  run: |
    echo "StateBind errors=${{ steps.statebind.outputs.errors }}"
    echo "StateBind warnings=${{ steps.statebind.outputs.warnings }}"
```

Available outputs are `passed`, `errors`, `warnings`, `exit_code`, `fail_on`,
`statebind_json`, `report`, `sarif`, `summary`, and `html-report`.

By default the action emits GitHub Actions annotations for every finding, so
warnings and errors appear directly in the workflow UI. Set
`annotations: "false"` to disable this behavior.

Add `policy: .statebind-policy.json` when the repository has team-specific
handoff requirements such as required roles or a minimum confidence level.

For this repository, the stricter gate is:

```yaml
- name: Run public-ready check
  run: bash scripts/check_public_ready.sh
```

That gate runs unit tests, the benchmark suite, the demo, the proof command,
and privacy-oriented public-release checks.

## Validation Report

`statebind validate --report statebind-validation.json` writes a stable JSON
report that can be uploaded as a CI artifact:

```json
{
  "schema_version": "0.1",
  "passed": true,
  "summary": {"errors": 0, "warnings": 4},
  "findings": []
}
```

When `--policy .statebind-policy.json` is provided, the report includes policy
findings such as `policy_missing_required_role` alongside structural findings.

Use `--fail-on error` for draft handoffs where warnings are acceptable. Use
`--fail-on warning` when the handoff is meant to be consumed by another agent
without manual cleanup.

## Markdown Summary

`statebind validate --summary statebind-summary.md` writes a compact Markdown
report for human review:

```markdown
# StateBind Guard

**Status:** PASS
**Contract:** `statebind.json`
**Fail on:** `warning`
**Findings:** 0 error(s), 0 warning(s)
```

## HTML Report

`statebind validate --html-report statebind-report.html` writes a standalone
HTML report for CI artifacts, release evidence, and human review:

```bash
statebind validate statebind.json \
  --repo . \
  --policy .statebind-policy.json \
  --fail-on warning \
  --html-report statebind-report.html
```

## GitHub Annotations

`statebind validate --github-annotations` prints workflow commands to stderr
without contaminating `--json` stdout:

```bash
statebind validate statebind.json \
  --repo . \
  --fail-on warning \
  --json \
  --github-annotations
```

## GitHub Outputs

`statebind validate --github-output "$GITHUB_OUTPUT"` appends stable workflow
outputs without requiring a downstream step to parse JSON:

```bash
statebind validate statebind.json \
  --repo . \
  --fail-on warning \
  --report statebind-validation.json \
  --github-output "$GITHUB_OUTPUT"
```

## Code Scanning Report

`statebind validate --sarif statebind-validation.sarif` writes a SARIF 2.1.0
report for GitHub code scanning. Each StateBind finding becomes a code-scanning
result on the handoff contract file, so ambiguous handles can appear next to
other PR annotations instead of staying hidden in CI logs.

Uploading SARIF requires `security-events: write` workflow permission on GitHub.
