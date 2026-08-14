"""Ledger CLI entry point. Implemented in Phase 2."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    print("ledger: not yet implemented (Phase 2)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
