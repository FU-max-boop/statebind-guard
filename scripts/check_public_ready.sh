#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[1/11] Checking for obvious local paths"
if grep -RIn --exclude-dir=.git --exclude-dir=build --exclude-dir=dist --exclude-dir='*.egg-info' --exclude='*.pdf' --exclude='*.zip' --exclude='*.whl' --exclude='*.tar.gz' --exclude='check_public_ready.sh' '/Users/fu\|/private/var/folders' .; then
  echo "Found local path leak." >&2
  exit 1
fi

echo "[2/11] Checking for common secret strings"
if grep -RIn --exclude-dir=.git --exclude-dir=build --exclude-dir=dist --exclude-dir='*.egg-info' --exclude='*.pdf' --exclude='*.zip' --exclude='*.whl' --exclude='*.tar.gz' --exclude='check_public_ready.sh' 'sk-[A-Za-z0-9]\|OPENAI_API_KEY=.*[A-Za-z0-9]\|ANTHROPIC_API_KEY=.*[A-Za-z0-9]' .; then
  echo "Found possible secret." >&2
  exit 1
fi

echo "[3/11] Running unit tests"
python -m unittest discover -s tests >/dev/null

echo "[4/11] Running skill smoke demo"
python statebind_handoff/statebind_handoff.py demo >/dev/null

echo "[5/11] Running self-contained proof"
python statebind_handoff/statebind_handoff.py proof >/dev/null
python statebind_handoff/statebind_handoff.py proof --json >/dev/null

echo "[6/11] Running schema compatibility check"
make schema-check >/dev/null

echo "[7/11] Running benchmark suite"
make benchmark >/dev/null

echo "[8/11] Regenerating adoption outreach packets"
make adoption-context-evidence >/dev/null
make adoption-feedback-requests >/dev/null

echo "[9/11] Running repository smoke test"
bash scripts/run_smoke_test.sh >/dev/null

echo "[10/11] Running package CLI smoke"
make package-check >/dev/null

echo "[11/11] Running release artifact smoke"
make dist-check >/dev/null

echo "Public-ready checks passed."
