#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Sprint-1 acceptance gate (Frozen). Console script from `pip install -e .`.
nre-verify-fixtures --all
