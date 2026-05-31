# Adoption Context Evidence: 2026-05-31

This is a pre-posting evidence card for StateBind Guard feedback-only
outreach. It records current public issue context so maintainer-facing
questions stay specific instead of generic.

**Source:** GitHub issue search and issue view via gh CLI

**Claim boundary:** These public issues are context for feedback-only outreach. They are not evidence that maintainers want StateBind Guard, and they do not authorize a code PR or CI adoption proposal.

## Posting Gate

- Use current issues only to make the feedback question specific.
- Do not comment on another issue unless the comment adds direct maintainer value.
- Do not present StateBind Guard as a fix for a target repository issue without a concrete patch or maintainer request.
- Preserve the human final-review gate before posting any public comment.

## Target Summary

| Repository | Decision | Issue Context | Current Read |
|---|---|---:|---|
| `pydantic/pydantic-ai` | `go_feedback_only` | 4 issues | Recent open issues show durable execution, message-history serialization, provider-valid histories, and state-loss boundaries are active project concerns. This strengthens the relevance of a narrow feedback request, but it still does not justify an adoption pitch. |
| `openai/openai-agents-python` | `go_feedback_only` | 4 issues | Recent and historical issues show active maintainer attention to RunState, handoff history, HITL resume, and active-run lifecycle boundaries. This supports a cautious feedback request, but the relationship bar is high and the ask should stay narrow. |

## `pydantic/pydantic-ai`

Recent open issues show durable execution, message-history serialization, provider-valid histories, and state-loss boundaries are active project concerns. This strengthens the relevance of a narrow feedback request, but it still does not justify an adoption pitch.

**Draft context sentence:**

> Before writing this, I also checked current public issue context, including #5731 and #5721. That made the executable handoff/state-binding question feel plausibly related, but I am not treating those issues as a request to adopt StateBind Guard.

| Issue | State | Labels | StateBind Relevance | Outreach Use |
|---|---|---|---|---|
| [#5731](https://github.com/pydantic/pydantic-ai/issues/5731) [roundtrip-sweep] _clean_message_history: conversation_id and metadata lost on round-trip | `open` | bug, durable exec, message history, state-loss | The reported boundary is exactly a durable resume/history case where identifiers remain visible but state needed for correlation is lost. | `draft_anchor` |
| [#5721](https://github.com/pydantic/pydantic-ai/issues/5721) [roundtrip-sweep] ModelResponsePart: `ToolReturnPart` with `part_kind='tool-return'` missing from discriminated union - breaks message history round-trip | `open` | bug, message history, serialization | Tool result identity survives in the narrative but fails the typed round-trip boundary, which is close to executable binding integrity. | `draft_anchor` |
| [#5637](https://github.com/pydantic/pydantic-ai/issues/5637) Expose public `message_history` validator for provider-valid histories | `open` | none | The issue asks for a reusable structural validator over message histories; StateBind Guard is adjacent but should be framed as external audit feedback, not a replacement. | `supporting_context` |
| [#3359](https://github.com/pydantic/pydantic-ai/issues/3359) History and Message (De)Serialization hooks to prevent hitting Temporal payload size limit | `open` | feature, temporal, message history | The discussion is about durable execution payload/history boundaries, showing the repo has real state-continuation pressure beyond generic agent instructions. | `supporting_context` |

## `openai/openai-agents-python`

Recent and historical issues show active maintainer attention to RunState, handoff history, HITL resume, and active-run lifecycle boundaries. This supports a cautious feedback request, but the relationship bar is high and the ask should stay narrow.

**Draft context sentence:**

> Before writing this, I also checked current public issue context, including #3319 and #3004. They made the handoff-history/RunState binding question feel plausibly related, but I am not suggesting a behavior change or default SDK integration.

| Issue | State | Labels | StateBind Relevance | Outreach Use |
|---|---|---|---|---|
| [#3319](https://github.com/openai/openai-agents-python/issues/3319) Nested handoff history flattening drops multiline and structured content | `closed` | feature:core | The issue is an explicit handoff-history integrity boundary where content shape is not preserved across chained handoffs. | `draft_anchor` |
| [#3004](https://github.com/openai/openai-agents-python/issues/3004) HITL resume drops tool output when parallel calls mix approval-gated and non-approval tools | `closed` | feature:core | The failure involves resume-time binding between a tool call and the output that must still be sent, which is close to StateBind Guard's role-to-handle boundary. | `draft_anchor` |
| [#3337](https://github.com/openai/openai-agents-python/issues/3337) RunState approval restore accepts invalid decision shapes | `closed` | feature:core | The issue concerns deserialization integrity of approval decisions, a state-resume boundary with safety implications. | `supporting_context` |
| [#798](https://github.com/openai/openai-agents-python/issues/798) Feature Request: Enhanced Run Lifecycle Management - Interrupt and Update Active Runs | `open` | enhancement, feature:core | The discussion asks for explicit active-run handles and step/state continuation, which is adjacent to executable handoff contracts. | `supporting_context` |

## Closeout Rule

If any target issue changes materially before posting, regenerate or manually
refresh this card. Treat stale context as a reason to hold outreach, not as
permission to post a generic note.
