# Adoption Examples

This page records public repositories that exercise StateBind Guard outside this
repository's own CI.

## Separate-Repository GitHub Action Receipt

The public adoption example lives at
[FU-max-boop/statebind-guard-adoption-example](https://github.com/FU-max-boop/statebind-guard-adoption-example).

What it proves:

- The workflow consumes a released action from a separate repository:
  `FU-max-boop/statebind-guard@v0.1.38`.
- The example stores `HANDOFF.md`, `statebind.json`, and a bug-fix policy.
- CI asserts the action outputs `passed=true`, `errors=0`, `warnings=0`, and
  `exit_code=0`.
- CI uploads JSON, SARIF, Markdown, and HTML validation reports.

Verified receipt:

- Workflow run:
  [26735088397](https://github.com/FU-max-boop/statebind-guard-adoption-example/actions/runs/26735088397)
- Commit:
  [ea607d4](https://github.com/FU-max-boop/statebind-guard-adoption-example/commit/ea607d4bb921d4be1f8734ce59b1ec48c39f51af)
- Artifact name: `statebind-validation`
- Result: `passed=true`, `errors=0`, `warnings=0`, `exit_code=0`

This is intentionally small. Its job is not to be a production application; its
job is to prove that the published composite action works when consumed across a
normal GitHub repository boundary.
