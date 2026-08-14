#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Ledger integrity gate — Regime B (ADR-002): no transform execution here.
#   1. append-only invariant for protected prefixes
#   2. frozen surface byte pins
#   3. full store audit (schema-gated manifests, object hashes, refs,
#      retraction records) — no replay
BASE="${1:-}"
if [ -n "$BASE" ]; then
  python3 tools/check_append_only.py "$BASE"
else
  python3 tools/check_append_only.py
fi
python3 tools/check_frozen.py
ledger fsck
