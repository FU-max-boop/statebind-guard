# Artifact Quality Gates

This project is judged by five practical gates.

## 1. Research Gate

Passes when a researcher can understand the thesis in 10 minutes:

- executable binding preservation is the core invariant
- visibility is not treated as binding
- StateBind is not framed as "RAG fails"
- limitations are explicit

## 2. Tool Gate

Passes when a coding-agent user can run the handoff helper in 5 minutes:

- `bash scripts/run_smoke_test.sh` works
- `python -m pip install -e .` exposes the `statebind` CLI
- `python statebind_handoff/statebind_handoff.py demo` works
- `HANDOFF.md` and `statebind.json` are produced
- `statebind validate statebind.json --repo . --fail-on error` runs
- uncertain handles are marked instead of invented

## 3. Evidence Gate

Passes when every binding has:

- semantic role
- exact executable handle
- evidence source
- confidence
- risk if ambiguous

## 4. Public-Release Gate

Passes when:

- no obvious local path, private email, or secret appears in tracked text files
- paper and supplement are included intentionally
- generated handoff files are gitignored
- public-ready check passes
- package metadata and console entry point are present

Run:

```bash
bash scripts/check_public_ready.sh
```

## 5. Outreach Gate

Passes when the repo supports a cold email or research discussion:

- README explains why this matters for coding agents
- `docs/research_brief.md` is readable without the full paper
- failure cases are concrete
- future directions invite collaboration rather than overclaiming
