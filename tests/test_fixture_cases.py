"""Frozen fixture cases: whole-envelope equality is the acceptance bar."""

from __future__ import annotations

from pathlib import Path

from nre.verify import engine
from nre.verify.fixtures import iter_case_dirs, run_case

EXPECTED_CASES = [
    "dss_requires_non_null_hash",
    "ok_minimal",
    "ok_payload_key_ordering",
    "schema_error_cap_missing_kind",
    "wss_hash_integrity_failed",
]


def test_all_cases_whole_envelope_equality(repo_root: Path) -> None:
    for case_dir in iter_case_dirs(repo_root):
        ok, actual, expected = run_case(repo_root, case_dir)
        assert actual == expected, f"envelope mismatch in {case_dir.name}"
        assert ok


def test_cases_iterated_in_lex_order(repo_root: Path) -> None:
    names = [d.name for d in iter_case_dirs(repo_root)]
    assert names == EXPECTED_CASES  # already lexicographic


def test_json_pointer_escaping() -> None:
    assert engine._json_pointer(["a/b", "c~d", 0]) == "/a~1b/c~0d/0"
    assert engine._json_pointer([]) == ""


def test_schema_error_sort_stable() -> None:
    errs = [
        {"doc": "wss", "path": "/b", "validator": "type", "message": "m2", "schema_path": "/x"},
        {"doc": "cap", "path": "/a", "validator": "required", "message": "m1", "schema_path": "/y"},
        {"doc": "cap", "path": "/a", "validator": "required", "message": "m0", "schema_path": "/z"},
    ]
    ordered = engine._sorted_schema_errors(errs)
    assert [e["message"] for e in ordered] == ["m0", "m1", "m2"]
