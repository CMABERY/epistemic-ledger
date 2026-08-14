#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Preflight — validate the same prerequisites the hosted jobs install
# (pinned deps + editable package + consistent dependency graph), so a
# stale environment fails loudly here instead of half-way through a gate.
for tool in python3 pytest ledger nre-verify-fixtures; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    {
      echo "error: '$tool' not on PATH."
      echo "  Activate the project venv and install pinned dependencies:"
      echo "    python -m venv .venv && . .venv/bin/activate"
      echo "    pip install -r requirements.lock && pip install -e . --no-deps"
    } >&2
    exit 3
  fi
done
python3 -m pip check

# Full local gate = exactly what CI runs, in order.
bash ci/run_tests.sh
bash ci/run_ledger_gate.sh "${1:-}"
bash ci/run_verify_fixtures.sh
echo "all gates: OK"
