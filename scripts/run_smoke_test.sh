#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

mkdir -p "$TMPDIR/src/api" "$TMPDIR/tests"
cp "$ROOT/examples/codex-handoff-demo/transcript.md" "$TMPDIR/transcript.md"
touch "$TMPDIR/src/api/router.py" "$TMPDIR/tests/test_router.py"

cd "$TMPDIR"
git init -q
git config user.email "demo@example.com"
git config user.name "Demo"
git add .
git commit -q -m init
printf '# demo change\n' >> src/api/router.py

python "$ROOT/statebind_handoff/statebind_handoff.py" extract \
  --repo . \
  --transcript transcript.md \
  --repo-label "." \
  --transcript-label "transcript.md" \
  --out HANDOFF.md \
  --json statebind.json

python "$ROOT/statebind_handoff/statebind_handoff.py" check HANDOFF.md
python "$ROOT/statebind_handoff/statebind_handoff.py" validate \
  statebind.json \
  --repo . \
  --fail-on error \
  --report statebind-validation.json

test -s statebind-validation.json

echo
echo "=== Generated HANDOFF.md preview ==="
sed -n '1,90p' HANDOFF.md
