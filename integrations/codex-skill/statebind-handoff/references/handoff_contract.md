# StateBind Handoff Contract

Use this reference when creating or auditing `HANDOFF.md` / `statebind.json`.

## Markdown Template

```markdown
# Agent Handoff

## Task
- Goal:
- Current status:
- Last confirmed good state:

## Active Target
- Type:
- Handle:
- Evidence:
- Confidence:

## Executable Bindings

| Role | Handle | Evidence | Confidence | Risk |
|---|---|---|---|---|
| working_directory |  |  |  |  |
| branch |  |  |  |  |
| current_patch_file |  |  |  |  |
| failing_test |  |  |  |  |
| next_command |  |  |  |  |
| related_pr_or_issue |  |  |  |  |
| comparison_commit_or_sha |  |  |  |  |

## Next Action
1.
2.
3.

## Do Not Touch / Avoid
-

## Risks And Ambiguities
-

## Resume Prompt
Paste this into the next coding-agent session:

> Continue this task from `HANDOFF.md` and `statebind.json`. First verify the working directory, branch, modified files, and bound commands. Only act on executable handles listed here unless newer evidence contradicts them. If any handle is missing or ambiguous, pause and repair the handoff before editing.
```

## Minimal JSON Shape

```json
{
  "schema_version": "0.1",
  "task": {
    "goal": "",
    "status": ""
  },
  "active_target": {
    "type": "",
    "handle": "",
    "evidence": "",
    "confidence": "high|medium|low|uncertain"
  },
  "bindings": [
    {
      "role": "current_patch_file",
      "handle": "src/example.py",
      "evidence": "git diff --name-only",
      "confidence": "high",
      "risk": ""
    }
  ],
  "risks": [],
  "resume_prompt": ""
}
```

Validate and write a CI-readable report:

```bash
python ~/.codex/skills/statebind-handoff/scripts/statebind_handoff.py validate \
  statebind.json \
  --repo . \
  --fail-on error \
  --report statebind-validation.json
```

## Common Roles

- `working_directory`
- `branch`
- `modified_file`
- `current_patch_file`
- `failing_test`
- `next_command`
- `test_output`
- `related_pr`
- `related_issue`
- `commit_sha`
- `branch_name`
- `dataset_version`
- `run_id`
- `config_path`
- `checkpoint_path`
- `artifact_path`

## Risk Taxonomy

- `missing_handle`: role is described but no exact executable handle is provided.
- `ambiguous_handle`: multiple plausible handles exist.
- `stale_handle`: handle may refer to old context.
- `unverified_handle`: handle was inferred from text but not checked locally.
- `wrong_role_risk`: a valid handle may belong to the wrong semantic role.
- `copy_only_risk`: a handle appears in context but is not bound to an active target.
- `unsafe_action_risk`: next command may mutate state or affect external systems.

## Resume Prompt Template

```text
You are resuming a coding-agent task.

First read HANDOFF.md and statebind.json.

Before editing, verify:
1. current working directory
2. git branch and status
3. all bound files exist
4. bound tests/commands are still relevant
5. no newer evidence contradicts the handoff

Use only the executable handles explicitly bound in the handoff unless you can verify a newer one.
If a handle is missing, stale, or ambiguous, pause and repair the handoff before acting.
```
