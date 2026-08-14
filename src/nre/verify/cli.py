"""nre-verify-fixtures — Sprint-1 acceptance gate.

Process exit codes (ADR-006): 0 OK, 2 usage, 20 FIXTURE_MISMATCH,
40 INTERNAL_ERROR. Envelope codes {0,10,11,12} live inside expected.json
comparisons and are never surfaced as process codes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from nre.exit_codes import PROC_INTERNAL_ERROR, PROC_USAGE
from nre.verify.fixtures import run_fixtures

_ANCHOR = Path("schemas") / "nre-artifacts-v1.0.2.schema.json"


def _discover_root(start: Path) -> Path | None:
    for p in (start, *start.parents):
        if (p / _ANCHOR).is_file():
            return p
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="nre-verify-fixtures",
        description="Run the frozen Sprint-1 vectors and fixture cases.",
    )
    ap.add_argument("--all", action="store_true", help="run all vectors + cases")
    ap.add_argument(
        "--case",
        action="append",
        metavar="NAME",
        help="run a single named case (repeatable); vectors always run",
    )
    ap.add_argument(
        "--trace-dir",
        metavar="DIR",
        help="write per-case actual envelopes as <case>.trace.json",
    )
    ap.add_argument("--fail-fast", action="store_true", help="stop at first mismatch")
    ap.add_argument(
        "--root",
        metavar="PATH",
        help="repo root (default: walk up from cwd to find the pinned schema)",
    )

    args = ap.parse_args(argv)

    if not args.all and not args.case:
        ap.print_help(sys.stderr)
        return PROC_USAGE

    root = Path(args.root).resolve() if args.root else _discover_root(Path.cwd())
    if root is None:
        print(
            f"error: could not locate repo root (no {_ANCHOR} above cwd); use --root",
            file=sys.stderr,
        )
        return PROC_USAGE

    trace_dir = Path(args.trace_dir).resolve() if args.trace_dir else None

    try:
        return run_fixtures(
            root,
            case_names=args.case,
            trace_dir=trace_dir,
            fail_fast=args.fail_fast,
        )
    except KeyboardInterrupt:
        return 130
    except KeyError as e:
        # Unknown case name is a usage error, not an internal error.
        print(f"error: {e.args[0] if e.args else e}", file=sys.stderr)
        return PROC_USAGE
    except Exception as e:  # noqa: BLE001 — gate must never crash silently
        print(f"INTERNAL_ERROR: {e}", file=sys.stderr)
        return PROC_INTERNAL_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
