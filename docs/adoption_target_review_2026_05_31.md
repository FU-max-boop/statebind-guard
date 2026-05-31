# Adoption Target Review: 2026-05-31

This review starts from the authenticated GitHub API scout campaign in
[`statebind_guard_github_scout_campaign_2026_05_31.md`](result_cards/statebind_guard_github_scout_campaign_2026_05_31.md).
It adds the human judgment gate before any maintainer outreach.

## Summary

- reviewed targets: 5
- feedback-only go: 2
- hold for more evidence: 3
- immediate generic outreach: 0

## Review Gate

- A high scout score is a triage signal, not permission to open an issue.
- Feedback-only outreach is acceptable only when the repository has explicit
  agent, handoff, durable-execution, or resume-state surfaces.
- Hold when the evidence is only generic `AGENTS.md` / `CLAUDE.md` presence.
- Do not propose a code PR before maintainer alignment unless there is a
  specific failing issue, test, or documented request.

## Target Decisions

| Repository | Scout | Decision | Confidence | First ask |
|---|---:|---|---|---|
| `pydantic/pydantic-ai` | 12 | `go_feedback_only` | high | Ask whether StateBind-style executable handoff contracts would help durable execution and agent-resume review. |
| `openai/openai-agents-python` | 12 | `go_feedback_only` | medium_high | Ask for feedback on handoff-history, RunState, and docs-example executable binding checks. |
| `modelcontextprotocol/python-sdk` | 10 | `hold_more_evidence` | medium | Wait for a concrete protocol-resume, session, or maintainer-risk case. |
| `browser-use/browser-use` | 10 | `hold_more_evidence` | medium | Find a concrete browser task resume, profile/session, or action-result binding failure first. |
| `OpenHands/OpenHands` | 9 | `hold_more_evidence` | medium | Review existing issues for task resume, workspace state, or pull request continuation failures before outreach. |

## Why These Two Are The First Feedback Targets

### `pydantic/pydantic-ai`

This is the strongest first target. Its root `AGENTS.md` explicitly treats
public APIs, abstractions, docs, and code as the product for both human and
agent users. More importantly, `pydantic_ai_slim/pydantic_ai/durable_exec/AGENTS.md`
names durable execution engines as first-class compatibility targets and calls
out preservation of run context, dependencies, message history, retries,
model/profile selection, and toolset lifecycle across durable boundaries.

That is close to StateBind Guard's core failure mode: preserving the binding
from active target to semantic role to executable handle when work continues
across an agent boundary.

Recommended first move: a short feedback request or proposal, not a PR.
The current public issue-context evidence for this target is recorded in
[`adoption_context_evidence_2026_05_31.md`](adoption_context_evidence_2026_05_31.md).

### `openai/openai-agents-python`

This is a strong fit but higher relationship bar. The repository has explicit
agent contribution instructions and a substantial `docs/handoffs.md` surface:
handoff inputs, input filters, nested handoff history, conversation-history
mapping, and RunState-adjacent workflow concerns. These are exactly the kind of
semantic boundaries where a visible identifier can be present but not bound to
the role the next agent must act on.

Recommended first move: ask whether a small external audit artifact is useful
for handoff-history / RunState / docs-example review. Do not imply the SDK
should adopt StateBind by default.
The current public issue-context evidence for this target is recorded in
[`adoption_context_evidence_2026_05_31.md`](adoption_context_evidence_2026_05_31.md).

## Why The Others Are Hold

`modelcontextprotocol/python-sdk`, `browser-use/browser-use`, and
`OpenHands/OpenHands` are plausible domains, but current evidence is too thin
for maintainer outreach. They need a concrete issue, failing resume case, or
documented state-continuation boundary before contact.

This is a deliberate reputation gate: the project should become known for
high-signal maintainer interactions, not for scanning repositories and opening
generic adoption requests.

## Draft Outreach Shape

Use this only after checking the current repository context:

```text
Hi, I maintain StateBind Guard, a small checker for coding-agent handoffs where
the transcript contains the right file/test/PR/SHA but fails to preserve which
one is bound to the active role.

I ran a read-only scout against this repo and noticed [specific surface]. I am
not asking you to adopt a dependency; I am trying to validate whether this
failure mode is real for maintainers of agent/durable-execution code.

Would a compact audit artifact that checks active-target -> role -> executable
handle bindings be useful for [specific review surface], or is this not a
problem you would want surfaced in CI/docs review?
```

Human final review is required before posting this publicly.
