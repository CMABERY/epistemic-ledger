"""Enforce the add-only invariant for protected ledger prefixes.

Ported from 4GARTHA ``tools/check_append_only.py`` (2ab510f); proven parsing
and decision logic kept intact. Deliberate changes:
  - protected prefixes extended per ADR-012 (deltas reserved, retractions),
  - explicit merge-base precheck with loud shallow-clone remediation (ADR-016),
  - root-commit handling (diff against the empty tree instead of failing).

For ``R*``/``C*`` lines BOTH old and new paths are checked. This is
non-negotiable; otherwise "rename out / rename back" defeats the invariant.

Exit codes: 0 OK, 2 violation, 3 git/usage failure.
"""

from __future__ import annotations

import argparse
import subprocess
import sys

PROTECTED_PREFIXES = (
    "ledger/objects/",
    "ledger/nodes/",
    "ledger/deltas/",
    "ledger/retractions/",
)


def _touches_protected(paths: list[str]) -> bool:
    return any(p.startswith(PROTECTED_PREFIXES) for p in paths)


def _parse_name_status_line(line: str) -> tuple[str, list[str]]:
    """Parse a single `git diff --name-status` line.

    Expected formats (tab-delimited):
      - "M\tpath"
      - "A\tpath"
      - "D\tpath"
      - "R100\told\tnew" (rename)
      - "C100\told\tnew" (copy)
    """
    parts = line.rstrip("\n").split("\t")
    if len(parts) < 2:
        # Extremely defensive: fall back to whitespace split.
        parts = line.split()
    status = parts[0]
    paths = [p for p in parts[1:] if p]
    return status, paths


def _git(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], text=True, stderr=subprocess.PIPE)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Enforce add-only invariant for protected ledger prefixes"
    )
    ap.add_argument(
        "base_ref", nargs="?", help="Base ref for diff range <base_ref>...HEAD"
    )
    ap.add_argument(
        "--cached",
        action="store_true",
        help="Check staged changes (for use in a pre-commit hook).",
    )
    args = ap.parse_args()

    if args.cached and args.base_ref:
        print("error: pass either base_ref OR --cached, not both", file=sys.stderr)
        return 3

    if args.cached:
        diff_cmd = ["git", "diff", "--cached", "--name-status"]
    elif args.base_ref:
        # ADR-016: fail loudly when no merge base exists, instead of letting
        # the diff silently compare garbage (historical --depth=1 bug).
        try:
            _git(["merge-base", args.base_ref, "HEAD"])
        except subprocess.CalledProcessError as e:
            print(
                f"error: no merge base between {args.base_ref!r} and HEAD.\n"
                "  Shallow clone? Fetch full history (actions/checkout with\n"
                "  fetch-depth: 0) or fetch the base ref explicitly.\n"
                f"  git said: {e.stderr.strip() if e.stderr else e}",
                file=sys.stderr,
            )
            return 3
        diff_cmd = ["git", "diff", "--name-status", f"{args.base_ref}...HEAD"]
    else:
        # Default range HEAD~1...HEAD; on a root commit diff the empty tree.
        try:
            _git(["rev-parse", "--verify", "--quiet", "HEAD~1"])
            diff_cmd = ["git", "diff", "--name-status", "HEAD~1...HEAD"]
        except subprocess.CalledProcessError:
            try:
                empty_tree = _git(["hash-object", "-t", "tree", "/dev/null"]).strip()
            except subprocess.CalledProcessError as e:
                print(f"failed computing empty tree hash: {e}", file=sys.stderr)
                return 3
            diff_cmd = ["git", "diff", "--name-status", empty_tree, "HEAD"]

    try:
        out = subprocess.check_output(diff_cmd, text=True)
    except Exception as e:
        print(f"failed running git diff: {e}", file=sys.stderr)
        return 3

    bad: list[tuple[str, list[str]]] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        status, paths = _parse_name_status_line(line)
        status_code = status[:1]  # e.g. "R" from "R100"

        if _touches_protected(paths):
            # Only additions are allowed under protected prefixes.
            # Renames/copies report two paths; treat those as violations.
            if status_code != "A":
                bad.append((status, paths))
            elif len(paths) != 1:
                # Extremely defensive: an "A" line is expected to have a single path.
                bad.append((status, paths))

    if bad:
        print(
            "append-only invariant violated "
            "(objects/nodes/deltas/retractions must be add-only):",
            file=sys.stderr,
        )
        for status, paths in bad:
            joined = "\t".join(paths)
            print(f"  {status}\t{joined}", file=sys.stderr)
        return 2

    print("append-only check: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
