# Roadmap

StateBind Guard is a public alpha. The roadmap is intentionally adoption-driven:
new work should reduce wrong-object agent actions, make the tool easier to wire
into real repositories, or improve the evidence behind the claim.

## Now

- Keep the CLI dependency-free and easy to inspect.
- Keep GitHub Action outputs, SARIF, Markdown, HTML, and JSON reports stable.
- Keep scenario policy presets practical for bug-fix, CI-failure, release,
  migration, and benchmark workflows.
- Collect adoption reports from coding-agent, CI, and research-engineering users.
- Collect sanitized visible-but-unbound failure cases for the benchmark corpus.

## Next

- Add adapters or examples for Codex, Claude Code, OpenHands, Cursor, and custom agent runners.
- Add report examples from third-party repositories.
- Add richer line/field localization in SARIF and GitHub annotations.

## Later

- Publish a larger natural deployed-agent handoff corpus when privacy constraints are solved.
- Compare StateBind-style contracts against memory/retrieval-only continuation baselines.
- Explore generated StateBind contracts from messy traces with human-verifiable evidence.
- Package stable releases through a standard package index once the interface settles.

## Non-Goals

- StateBind Guard will not claim to solve all agent memory, planning, or retrieval failures.
- The validator should stay conservative rather than infer semantic bindings from vague prose.
- Public benchmark additions should be sanitized and reviewable, not scraped private traces.
