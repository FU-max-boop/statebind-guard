#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${CODEX_HOME:-$HOME/.codex}/skills/statebind-handoff"

mkdir -p "$(dirname "$DEST")"
rm -rf "$DEST"
cp -R "$ROOT/integrations/codex-skill/statebind-handoff" "$DEST"

echo "Installed statebind-handoff skill to: $DEST"
echo "Try: Use statebind-handoff to create a HANDOFF.md for this coding task."

