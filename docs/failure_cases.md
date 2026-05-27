# Failure Cases

These are small, readable examples of executable binding failures.

## Case 1: Gold ID Visible, Wrong Role

The handoff contains both `head_sha=abc1234` and `base_sha=def5678`. The next task asks for the comparison base, but the resumed agent copies the head SHA.

Failure type: `right record, wrong role`.

StateBind repair:

```text
active target: PR #42
role: comparison_base_sha
handle: def5678
```

## Case 2: File Mentioned, Wrong Active File

The transcript mentions `src/legacy/router_old.py` and `src/api/router.py`. The active patch is in `src/api/router.py`, but the handoff only says "the router file".

Failure type: `ambiguous handle`.

StateBind repair:

```text
role: current_patch_file
handle: src/api/router.py
evidence: git diff --name-only
```

## Case 3: Test Described But Not Executable

The summary says "rerun the streaming test", but does not preserve the exact test selector.

Failure type: `missing executable handle`.

StateBind repair:

```text
role: failing_test
handle: pytest tests/test_router.py::test_stream_response
```

## Case 4: Stale Commit Copied

The context includes an old commit SHA from earlier discussion. The resumed agent copies it because it is visible and plausible.

Failure type: `stale handle`.

StateBind repair:

```text
role: current_head_sha
handle: abc1234
evidence: latest PR metadata row
risk: do not use stale SHA 999aaaa
```

## Case 5: Command Exists But Wrong Working Directory

The command is correct, but the handoff does not bind the working directory. The resumed agent runs it from the wrong repo root.

Failure type: `missing environment binding`.

StateBind repair:

```text
role: working_directory
handle: repository root
evidence: pwd / git rev-parse --show-toplevel
```

