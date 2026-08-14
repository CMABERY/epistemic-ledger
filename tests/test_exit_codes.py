"""Process-level exit-code contract of nre-verify-fixtures (ADR-006).

Envelope codes {0,10,11,12} are frozen by fixture bytes and tested via
whole-envelope equality; these tests cover the process layer:
0 OK / 2 usage / 20 FIXTURE_MISMATCH / 40 INTERNAL_ERROR.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from nre.verify.cli import main


def _tmp_root(repo_root: Path, tmp_path: Path) -> Path:
    for d in ("schemas", "fixtures"):
        shutil.copytree(repo_root / d, tmp_path / d)
    return tmp_path


def test_all_pristine_ok(repo_root: Path, capsys: pytest.CaptureFixture) -> None:
    assert main(["--all", "--root", str(repo_root)]) == 0
    assert "fixtures: OK (5 cases)" in capsys.readouterr().out


def test_no_args_usage(capsys: pytest.CaptureFixture) -> None:
    assert main([]) == 2


def test_single_case_ok(repo_root: Path, capsys: pytest.CaptureFixture) -> None:
    assert main(["--case", "ok_minimal", "--root", str(repo_root)]) == 0
    assert "fixtures: OK (1 cases)" in capsys.readouterr().out


def test_unknown_case_usage(repo_root: Path, capsys: pytest.CaptureFixture) -> None:
    assert main(["--case", "no_such_case", "--root", str(repo_root)]) == 2


def test_corrupted_vector_mismatch(repo_root: Path, tmp_path: Path, capsys) -> None:
    root = _tmp_root(repo_root, tmp_path)
    vec = root / "fixtures" / "vectors" / "strings.json"
    data = json.loads(vec.read_text(encoding="utf-8"))
    data["tests"][0]["expect"] = "WRONG"
    vec.write_text(json.dumps(data), encoding="utf-8")
    assert main(["--all", "--root", str(root)]) == 20
    assert "VECTOR_FAIL" in capsys.readouterr().err


def test_corrupted_expected_mismatch(repo_root: Path, tmp_path: Path, capsys) -> None:
    root = _tmp_root(repo_root, tmp_path)
    exp = root / "fixtures" / "cases" / "ok_minimal" / "expected.json"
    data = json.loads(exp.read_text(encoding="utf-8"))
    data["verify"]["exit_code"] = 11
    exp.write_text(json.dumps(data), encoding="utf-8")
    assert main(["--all", "--root", str(root)]) == 20
    assert "CASE_MISMATCH: ok_minimal" in capsys.readouterr().err


def test_missing_schema_internal_error(repo_root: Path, tmp_path: Path, capsys) -> None:
    root = _tmp_root(repo_root, tmp_path)
    (root / "schemas" / "nre-artifacts-v1.0.2.schema.json").unlink()
    assert main(["--all", "--root", str(root)]) == 40
    assert "INTERNAL_ERROR" in capsys.readouterr().err


def test_schema_pin_mismatch_internal_error(repo_root: Path, tmp_path: Path, capsys) -> None:
    root = _tmp_root(repo_root, tmp_path)
    (root / "schemas" / "SCHEMA_SHA256").write_text("0" * 64 + "\n", encoding="utf-8")
    assert main(["--all", "--root", str(root)]) == 40
    assert "INTERNAL_ERROR" in capsys.readouterr().err


def test_trace_dir_writes_envelopes(repo_root: Path, tmp_path: Path, capsys) -> None:
    trace_dir = tmp_path / "traces"
    assert main(["--all", "--root", str(repo_root), "--trace-dir", str(trace_dir)]) == 0
    written = sorted(p.name for p in trace_dir.iterdir())
    assert written == [
        "dss_requires_non_null_hash.trace.json",
        "ok_minimal.trace.json",
        "ok_payload_key_ordering.trace.json",
        "schema_error_cap_missing_kind.trace.json",
        "wss_hash_integrity_failed.trace.json",
    ]
    # Trace content equals the frozen expected envelope for a pristine tree.
    got = json.loads((trace_dir / "ok_minimal.trace.json").read_text(encoding="utf-8"))
    exp = json.loads(
        (repo_root / "fixtures" / "cases" / "ok_minimal" / "expected.json").read_text(
            encoding="utf-8"
        )
    )
    assert got == exp
