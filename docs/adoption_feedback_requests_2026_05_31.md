# Adoption Feedback Requests: 2026-05-31

These are human-reviewed feedback-only drafts generated from
`data/statebind_guard_github_scout_campaign_2026_05_31.json` and the target-review packet.

They are intentionally not ready-to-post automation. A human should read
the current repository context, trim wording, and only then decide whether
to publish from their own account.

## Posting Gate

- Do not treat a high scout score as permission to open a maintainer issue.
- Prefer feedback-only outreach when a repository has explicit agent or durable-execution surfaces.
- Hold when the scout finds only generic agent instruction files but no concrete handoff or resume boundary.
- Do not propose a code PR before maintainer alignment unless there is a specific failing issue, test, or documented request.
- Do not post any draft whose target review decision is not `go_feedback_only`.
- Do not include generated text verbatim if it sounds broader than the maintainer's actual problem.
- Human final review is required before posting any public comment.

## Draft Summary

| Repository | Decision | Confidence | Evidence |
|---|---|---|---|
| `pydantic/pydantic-ai` | `go_feedback_only` | high | AGENTS.md, pydantic_ai_slim/pydantic_ai/durable_exec/AGENTS.md |
| `openai/openai-agents-python` | `go_feedback_only` | medium_high | AGENTS.md, docs/handoffs.md |

## Feedback-Only Drafts

### Draft For `pydantic/pydantic-ai`

**Suggested title:** Feedback request: executable handoff boundaries in `pydantic-ai`

```text
Hi pydantic-ai maintainers,

I maintain StateBind Guard, a small open-source checker for one coding-agent
handoff failure mode: a transcript or summary can contain the right file, test,
pull request, or commit, but still fail to preserve which handle is bound to the
active role the next agent must act on.

I ran a read-only StateBind scout and then did a human review before deciding
whether to ask for feedback here. The relevant surfaces I saw were `AGENTS.md`, `pydantic_ai_slim/pydantic_ai/durable_exec/AGENTS.md`.

I am not asking you to adopt a dependency or wire CI. My narrow question is:
Would a StateBind-style executable handoff contract be useful as a review or audit artifact for durable execution and agent-resume boundaries?

If this is not a problem you want surfaced, that is useful feedback too. If it
is relevant, what would be the least noisy artifact for maintainers to review:
a short issue template, a docs-only checklist, a CI warning, or something else?
```

**Why this target is cleared for feedback:** The repository explicitly frames public APIs, docs, and agent-facing contribution quality as product quality. Its durable execution guidelines call out preserving run context, dependencies, message history, retries, model/profile selection, and toolset lifecycle across durable boundaries, which is close to StateBind Guard's executable-binding failure mode.

**Do not do:**
- Do not open a code PR before a proposal or maintainer reply.
- Do not claim Pydantic AI needs StateBind Guard.
- Do not suggest broad adoption across the whole repo from the first contact.

### Draft For `openai/openai-agents-python`

**Suggested title:** Feedback request: executable handoff boundaries in `openai-agents-python`

```text
Hi openai-agents-python maintainers,

I maintain StateBind Guard, a small open-source checker for one coding-agent
handoff failure mode: a transcript or summary can contain the right file, test,
pull request, or commit, but still fail to preserve which handle is bound to the
active role the next agent must act on.

I ran a read-only StateBind scout and then did a human review before deciding
whether to ask for feedback here. The relevant surfaces I saw were `AGENTS.md`, `docs/handoffs.md`.

I am not asking you to adopt a dependency or wire CI. My narrow question is:
Would executable binding checks be useful for handoff-history, RunState, or docs-example review, or is this outside the problems maintainers want surfaced?

If this is not a problem you want surfaced, that is useful feedback too. If it
is relevant, what would be the least noisy artifact for maintainers to review:
a short issue template, a docs-only checklist, a CI warning, or something else?
```

**Why this target is cleared for feedback:** The repository contains explicit contributor-agent instructions plus a substantial handoffs documentation surface. The docs discuss handoff inputs, input filters, nested handoff history, and conversation-history mapping, all of which create semantic-role-to-executable-state boundaries that StateBind Guard is designed to audit.

**Do not do:**
- Do not propose changing SDK behavior without an issue and maintainer alignment.
- Do not edit generated translated docs.
- Do not imply official OpenAI endorsement.

## Hold Targets

| Repository | Decision | Evidence Needed |
|---|---|---|
| `modelcontextprotocol/python-sdk` | `hold_more_evidence` | Hold until there is a specific issue, PR, or protocol-resume case where executable bindings would reduce maintainer risk. |
| `browser-use/browser-use` | `hold_more_evidence` | Hold until a specific browser task resume, profile/session, or action-result binding example is found. |
| `OpenHands/OpenHands` | `hold_more_evidence` | Review existing OpenHands issues and docs for concrete task resume, workspace state, or pull request continuation failures before any outreach. |

## Manual Closeout Checklist

- Re-check the target repository's current issues and contribution rules.
- Remove any claim that cannot be tied to a specific target path or doc.
- Keep the ask to feedback, not adoption.
- Record any maintainer reply as an external signal only after it exists publicly.
