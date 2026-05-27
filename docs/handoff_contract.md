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

