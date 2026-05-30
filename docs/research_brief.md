# StateBindBench: One-Page Research Brief

## Problem

Coding agents resume long-running software work from summaries, retrieval contexts, memory files, and tool traces. These handoffs often preserve relevant context but lose the executable binding needed for safe continuation.

## Key Insight

Identifier visibility is not executable binding. A model can see the correct file path, command, PR, issue, or commit SHA and still choose the wrong one if the active target and semantic role are not bound.

## Contribution

StateBindBench frames executable binding preservation as an interaction-aware evaluation target for coding-agent handoffs.

```text
active target -> semantic role -> executable handle
```

## Artifact

This repository includes:

- failure cases
- seed, natural-handoff, multi-category failure-corpus, and deployed-derived
  benchmark snippets
- baseline and StateBind Guard result cards
- a lightweight handoff helper
- a versioned `statebind.json` schema and CI validation report
- an installable Codex skill for creating and checking executable handoffs

## Why It Matters

Reliable coding agents need more than memory recall or context retrieval. They need handoff interfaces that preserve actionability: which object to edit, which command to run, which commit to compare, and which artifact is current.

## Next Directions

- larger deployed-agent handoff corpus from real sessions and external adopters
- learned StateBind construction
- binding-aware memory/RAG interfaces
- coding-agent safety evaluation for wrong-object actions
- integrations with Codex, Claude Code, Cursor, and OpenHands
