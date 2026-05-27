# StateBindBench Short Talk

## Slide 1: Problem

Coding agents need to resume long-running tasks from handoff artifacts.

But summaries and retrieval contexts often preserve narrative context without preserving executable state.

## Slide 2: Key Insight

Visibility is not binding.

The right identifier can appear in context while the agent binds it to the wrong target or role.

## Slide 3: StateBind

Minimal executable handoff unit:

```text
active target -> semantic role -> executable handle
```

Examples:

- PR -> comparison base -> commit SHA
- task -> failing test -> pytest selector
- patch -> active file -> file path

## Slide 4: Artifact

StateBindBench includes:

- benchmark supplement
- failure cases
- exact-ID handoff diagnostics
- Codex-compatible handoff skill
- smoke-testable local helper

## Slide 5: Future Work

- Natural deployed-agent handoff corpus
- Learned binding construction from messy traces
- Binding-aware memory for coding agents
- Safety evaluation for wrong-object actions

