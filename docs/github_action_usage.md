# GitHub Action Usage

Use this as a smoke gate when a repository stores coding-agent handoffs such as
`HANDOFF.md`, `AGENT_HANDOFF.md`, or `docs/handoff.md`.

```yaml
name: statebind-guard

on:
  pull_request:
  push:

jobs:
  statebind-guard:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install StateBind Guard
        run: python -m pip install -e .
      - name: Check handoff markdown
        run: statebind check HANDOFF.md
      - name: Validate machine-readable bindings
        run: |
          statebind validate statebind.json \
            --repo . \
            --fail-on warning \
            --json \
            --report statebind-validation.json
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: statebind-validation
          path: statebind-validation.json
```

For this repository, the stricter gate is:

```yaml
- name: Run public-ready check
  run: bash scripts/check_public_ready.sh
```

That gate runs unit tests, the benchmark suite, the demo, and privacy-oriented
public-release checks.

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

Use `--fail-on error` for draft handoffs where warnings are acceptable. Use
`--fail-on warning` when the handoff is meant to be consumed by another agent
without manual cleanup.
