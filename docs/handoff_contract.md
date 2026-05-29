# Handoff Contract

The minimal StateBind unit is:

```text
active target -> semantic role -> executable handle
```

Recommended `HANDOFF.md` fields:

```text
Task
Active Target
Executable Bindings
Next Action
Do Not Touch / Avoid
Risks And Ambiguities
Resume Prompt
```

Recommended binding fields:

```text
role
handle
evidence
confidence
risk
```

Confidence values:

```text
high
medium
low
uncertain
```

Never silently promote an uncertain handle to a high-confidence action target.

## Machine-Readable Contract

`statebind.json` is the CI-facing form of the same contract:

```json
{
  "schema_version": "0.1",
  "task": {
    "goal": "fix failing streaming test",
    "status": "patch ready; rerun focused test"
  },
  "active_target": {
    "type": "test",
    "handle": "pytest tests/test_router.py::test_stream_response",
    "evidence": "last red CI job",
    "confidence": "high"
  },
  "bindings": [
    {
      "role": "failing_test",
      "handle": "pytest tests/test_router.py::test_stream_response",
      "evidence": "terminal output from last failing run",
      "confidence": "high",
      "risk": ""
    }
  ],
  "risks": []
}
```

Validate it with:

```bash
statebind validate statebind.json --repo . --fail-on error --report statebind-validation.json
```

For strict CI, use:

```bash
statebind validate statebind.json --repo . --fail-on warning --json --report statebind-validation.json
```

The validator checks structure, exact handles, confidence labels, vague
references such as "the previous command", and path-like handles that no longer
exist in the repository. It does not claim to prove semantic correctness; it is
a guard against unsafe handoff shape.

The tracked schema is `schemas/statebind.schema.json`. Print the validator's
built-in schema with:

```bash
statebind schema
```
