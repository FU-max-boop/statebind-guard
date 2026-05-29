#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "[1/7] Checking for obvious local paths"
if grep -RIn --exclude-dir=.git --exclude='*.pdf' --exclude='*.zip' --exclude='check_public_ready.sh' '/Users/fu\|/private/var/folders' .; then
  echo "Found local path leak." >&2
  exit 1
fi

echo "[2/7] Checking for common secret strings"
if grep -RIn --exclude-dir=.git --exclude='*.pdf' --exclude='*.zip' --exclude='check_public_ready.sh' 'sk-[A-Za-z0-9]\|OPENAI_API_KEY=.*[A-Za-z0-9]\|ANTHROPIC_API_KEY=.*[A-Za-z0-9]' .; then
  echo "Found possible secret." >&2
  exit 1
fi

echo "[3/7] Running unit tests"
python -m unittest discover -s tests >/dev/null

echo "[4/7] Running skill smoke demo"
python statebind_handoff/statebind_handoff.py demo >/dev/null

echo "[5/7] Running benchmark suite"
make benchmark >/dev/null

echo "[6/7] Running repository smoke test"
bash scripts/run_smoke_test.sh >/dev/null

echo "[7/7] Running package CLI smoke"
python -m pip install -e . >/dev/null
statebind demo >/dev/null
statebind --help >/dev/null

echo "Public-ready checks passed."
