# Visible ID But Unbound

This example illustrates the core failure mode.

The context may mention multiple valid identifiers:

```text
head SHA: abc1234
base SHA: def5678
stale SHA: 999aaaa
```

A vague handoff says:

```text
Continue from the PR and use the SHA above.
```

The next agent can see the correct string but still choose the wrong role.

A StateBind handoff preserves the typed binding:

```text
active target: PR #42
semantic role: comparison base
executable handle: def5678
```

The point is not that retrieval never works. The point is that visibility alone is not the same as binding preservation.

