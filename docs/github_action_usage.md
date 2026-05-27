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
      - name: Check handoff
        run: |
          python statebind_handoff/statebind_handoff.py check HANDOFF.md
```

For this repository, the stricter gate is:

```yaml
- name: Run public-ready check
  run: bash scripts/check_public_ready.sh
```

That gate runs unit tests, the benchmark suite, the demo, and privacy-oriented
public-release checks.
