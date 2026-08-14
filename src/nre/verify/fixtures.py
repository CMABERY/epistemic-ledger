"""Deterministic fixture runner: vectors first, then cases in lex order.

Ported from 4GARTHA `verify/verify.py` (2ab510f) with non-frozen extensions:
case selection, trace output, fail-fast (flags are not frozen; `--all`
behavior is bit-identical to the original).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from nre.canon.fileref import file_ref
from nre.canon.hashing import canon_json_bytes, sha256_prefixed
from nre.canon.strings import normalize_string
from nre.exit_codes import PROC_FIXTURE_MISMATCH, PROC_OK
from nre.verify.engine import verify_triplet


def _raw_sha256_prefixed(p: Path) -> str:
    return file_ref(p).raw_sha256


def _load_json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def iter_case_dirs(repo_root: Path, names: Sequence[str] | None = None) -> List[Path]:
    """All case directories in lexicographic order; optionally a named subset.

    Raises KeyError for a requested name that does not exist.
    """

    cases_root = repo_root / "fixtures" / "cases"
    all_dirs = sorted(
        (p for p in cases_root.iterdir() if p.is_dir()), key=lambda p: p.name
    )
    if names is None:
        return all_dirs
    by_name = {p.name: p for p in all_dirs}
    missing = [n for n in names if n not in by_name]
    if missing:
        raise KeyError(f"unknown fixture case(s): {', '.join(sorted(missing))}")
    return [by_name[n] for n in sorted(set(names))]


def run_vectors(repo_root: Path) -> List[str]:
    """Run P1/P2/P3 micro-vectors. Returns failure strings (empty if OK)."""

    failures: List[str] = []
    vectors_dir = repo_root / "fixtures" / "vectors"

    strings_vec = _load_json(vectors_dir / "strings.json")
    for i, t in enumerate(strings_vec.get("tests", [])):
        got = normalize_string(t["in"])
        if got != t["expect"]:
            failures.append(f"strings[{i}]: expected {t['expect']!r}, got {got!r}")

    ids_vec = _load_json(vectors_dir / "ids.json")
    for i, t in enumerate(ids_vec.get("tests", [])):
        got = sha256_prefixed(canon_json_bytes(t["obj"]))
        if got != t["expect"]:
            failures.append(f"ids[{i}]: expected {t['expect']!r}, got {got!r}")

    fileref_vec = _load_json(vectors_dir / "fileref.json")
    for i, t in enumerate(fileref_vec.get("tests", [])):
        got = file_ref(vectors_dir / t["path"]).raw_sha256
        if got != t["expect"]:
            failures.append(f"fileref[{i}]: expected {t['expect']!r}, got {got!r}")

    return failures


def run_case(repo_root: Path, case_dir: Path) -> Tuple[bool, Dict[str, Any], Dict[str, Any]]:
    """Run a single fixture case. Returns (ok, actual_envelope, expected_envelope)."""

    cap_p = case_dir / "cap.json"
    wss_p = case_dir / "wss.json"
    dss_p = case_dir / "dss.json"
    exp_p = case_dir / "expected.json"

    trace = {
        "case": case_dir.name,
        "inputs": {
            "cap": {"raw_sha256": _raw_sha256_prefixed(cap_p)},
            "wss": {"raw_sha256": _raw_sha256_prefixed(wss_p)},
            "dss": {"raw_sha256": _raw_sha256_prefixed(dss_p)},
        },
    }

    cap = _load_json(cap_p)
    wss = _load_json(wss_p)
    dss = _load_json(dss_p)

    env = verify_triplet(repo_root, cap, wss, dss).to_json()
    actual: Dict[str, Any] = {"trace": trace, "verify": env}

    expected: Dict[str, Any] = _load_json(exp_p)

    return actual == expected, actual, expected


def run_fixtures(
    repo_root: Path,
    case_names: Sequence[str] | None = None,
    trace_dir: Path | None = None,
    fail_fast: bool = False,
) -> int:
    """Run vectors then fixture cases in deterministic order."""

    v_fail = run_vectors(repo_root)
    if v_fail:
        for f in v_fail:
            print(f"VECTOR_FAIL: {f}", file=sys.stderr)
        return PROC_FIXTURE_MISMATCH

    case_dirs = iter_case_dirs(repo_root, case_names)

    if trace_dir is not None:
        trace_dir.mkdir(parents=True, exist_ok=True)

    mismatches: List[str] = []
    for case_dir in case_dirs:
        ok, actual, expected = run_case(repo_root, case_dir)
        if trace_dir is not None:
            out = trace_dir / f"{case_dir.name}.trace.json"
            out.write_text(
                json.dumps(actual, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        if not ok:
            mismatches.append(case_dir.name)
            print(f"CASE_MISMATCH: {case_dir.name}", file=sys.stderr)
            print("--- expected", file=sys.stderr)
            print(json.dumps(expected, indent=2, sort_keys=True), file=sys.stderr)
            print("--- actual", file=sys.stderr)
            print(json.dumps(actual, indent=2, sort_keys=True), file=sys.stderr)
            if fail_fast:
                break

    if mismatches:
        print(f"mismatched cases: {', '.join(sorted(mismatches))}", file=sys.stderr)
        return PROC_FIXTURE_MISMATCH

    print(f"fixtures: OK ({len(case_dirs)} cases)")
    return PROC_OK
