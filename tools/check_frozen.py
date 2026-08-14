"""Verify the byte-pinned frozen surface (ADR-014).

Every file listed in ``fixtures/FROZEN_SHA256SUMS`` must hash to its pinned
digest. Changing frozen bytes therefore requires touching the sums file —
loud and reviewable.

Exit codes: 0 OK, 2 mismatch/missing, 3 internal failure.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> int:
    root = repo_root_from_script()
    sums_path = root / "fixtures" / "FROZEN_SHA256SUMS"
    try:
        lines = [
            ln
            for ln in sums_path.read_text(encoding="utf-8").splitlines()
            if ln.strip()
        ]
    except OSError as e:
        print(f"failed reading {sums_path}: {e}", file=sys.stderr)
        return 3

    bad: list[str] = []
    for line in lines:
        try:
            digest, rel = line.split(maxsplit=1)
        except ValueError:
            bad.append(f"malformed line: {line!r}")
            continue
        p = root / rel.strip()
        if not p.is_file():
            bad.append(f"missing frozen file: {rel.strip()}")
            continue
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        if actual != digest:
            bad.append(f"frozen bytes changed: {rel.strip()} (got {actual})")

    if bad:
        print("frozen surface check failed:", file=sys.stderr)
        for b in bad:
            print(f"  {b}", file=sys.stderr)
        return 2

    print(f"frozen surface check: OK ({len(lines)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
