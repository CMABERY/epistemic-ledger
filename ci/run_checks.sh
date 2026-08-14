#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Full local gate = exactly what CI runs, in order.
bash ci/run_tests.sh
bash ci/run_ledger_gate.sh "${1:-}"
bash ci/run_verify_fixtures.sh
echo "all gates: OK"
