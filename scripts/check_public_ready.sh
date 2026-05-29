#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[1/8] Checking for obvious local paths"
if grep -RIn --exclude-dir=.git --exclude='*.pdf' --exclude='*.zip' --exclude='check_public_ready.sh' '/Users/fu\|/private/var/folders' .; then
  echo "Found local path leak." >&2
  exit 1
fi

echo "[2/8] Checking for common secret strings"
if grep -RIn --exclude-dir=.git --exclude='*.pdf' --exclude='*.zip' --exclude='check_public_ready.sh' 'sk-[A-Za-z0-9]\|OPENAI_API_KEY=.*[A-Za-z0-9]\|ANTHROPIC_API_KEY=.*[A-Za-z0-9]' .; then
  echo "Found possible secret." >&2
  exit 1
fi

echo "[3/8] Running unit tests"
python -m unittest discover -s tests >/dev/null

echo "[4/8] Running skill smoke demo"
python statebind_handoff/statebind_handoff.py demo >/dev/null

echo "[5/8] Running schema compatibility check"
make schema-check >/dev/null

echo "[6/8] Running benchmark suite"
make benchmark >/dev/null

echo "[7/8] Running repository smoke test"
bash scripts/run_smoke_test.sh >/dev/null

echo "[8/8] Running package CLI smoke"
make package-check >/dev/null

echo "Public-ready checks passed."
