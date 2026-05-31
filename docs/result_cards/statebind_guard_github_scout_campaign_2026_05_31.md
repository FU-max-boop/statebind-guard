# StateBind Scout Result Card

## Scope

- repositories scanned: 8
- successful audits: 8
- failed audits: 0
- generated maintainer-note drafts: 7

## Priority Mix

| Priority | Count |
|---|---:|
| `high` | 7 |
| `medium` | 0 |
| `low` | 0 |
| `follow_up` | 0 |
| `skip` | 1 |

## Top Review Targets

| Repository | Priority | Score | Candidates | Suggested gate | Why now |
|---|---|---:|---:|---|---|
| `openai-agents-python` | `high` | 12 | 16 | `python -m pytest` | handoff surfaces exist but StateBind is not fully wired; 16 handoff-like file(s) found |
| `pydantic-ai` | `high` | 12 | 19 | `make test` | handoff surfaces exist but StateBind is not fully wired; 19 handoff-like file(s) found |
| `python-sdk` | `high` | 10 | 2 | `python -m pytest` | handoff surfaces exist but StateBind is not fully wired; 2 handoff-like file(s) found |
| `browser-use` | `high` | 10 | 2 | `python -m pytest` | handoff surfaces exist but StateBind is not fully wired; 2 handoff-like file(s) found |
| `OpenHands` | `high` | 9 | 1 | `make test` | handoff surfaces exist but StateBind is not fully wired; 1 handoff-like file(s) found |
| `crewAI` | `high` | 9 | 1 | `python -m pytest` | handoff surfaces exist but StateBind is not fully wired; 1 handoff-like file(s) found |
| `autogen` | `high` | 8 | 3 | `make test` | handoff surfaces exist but StateBind is not fully wired; 3 handoff-like file(s) found |

## Review Gate

- Treat this card as a triage artifact, not as permission to spam maintainers.
- Prefer high or medium targets with handoff-like files and an inferred local gate.
- Read the repository context before opening an issue or PR.
- Convert generated notes into human-reviewed, maintainer-specific feedback.

## Claim Boundary

This card proves the scout can find plausible adoption surfaces. It does not prove that a maintainer wants StateBind, that a repository has a real handoff failure, or that outreach should be opened without project-specific review.
