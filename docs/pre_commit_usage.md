# Pre-Commit Usage

StateBind Guard can run through the standard
[pre-commit](https://pre-commit.com/) framework.

Add this to your repository's `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/FU-max-boop/statebind-guard
    rev: v0.1.32
    hooks:
      - id: statebind-guard
```

Then install and run:

```bash
pre-commit install
pre-commit run statebind-guard --all-files
```

The hook validates `statebind.json` with:

```bash
statebind validate statebind.json --repo . --fail-on warning --quiet
```

It runs even when no filenames are passed, because the executable handoff
contract is a repository-level safety check rather than a per-file formatter.

Verify the full local setup with:

```bash
statebind doctor --repo .
```

For teams that do not use pre-commit, use the built-in local installer instead:

```bash
statebind install-hook --fail-on warning --policy .statebind-policy.json
statebind doctor --repo .
```

The built-in hook accepts `--policy` so local commits can enforce the same
required roles and confidence floor as CI.
