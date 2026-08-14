from __future__ import annotations

from pathlib import Path

import pytest

from ledger.cli import main


@pytest.fixture
def in_repo(ledger_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(ledger_repo)
    return ledger_repo


def _mk(tmp_path: Path, name: str, content: bytes) -> Path:
    p = tmp_path / name
    p.write_bytes(content)
    return p


def test_hash(in_repo: Path, tmp_path: Path, capsys) -> None:
    src = _mk(tmp_path, "a.bin", b"data")
    assert main(["hash", str(src)]) == 0
    out = capsys.readouterr().out.strip()
    assert len(out) == 64


def test_ingest_root_and_verify(in_repo: Path, tmp_path: Path, capsys) -> None:
    src = _mk(tmp_path, "a.bin", b"root artifact")
    assert main(["ingest", str(src), "--note", "first root"]) == 0
    nid = capsys.readouterr().out.strip()
    assert len(nid) == 64

    assert main(["verify", nid]) == 0
    assert "OK" in capsys.readouterr().out

    assert main(["refs", "set", "main", nid]) == 0
    assert main(["refs", "get", "main"]) == 0
    assert capsys.readouterr().out.strip() == nid

    # verify-reachable defaults to ref 'main'
    assert main(["verify-reachable"]) == 0


def test_ingest_derived_requires_transform_file(in_repo: Path, tmp_path: Path, capsys) -> None:
    src = _mk(tmp_path, "a.bin", b"root")
    assert main(["ingest", str(src)]) == 0
    parent = capsys.readouterr().out.strip()

    child = _mk(tmp_path, "b.bin", b"derived")
    with pytest.raises(SystemExit, match="ADR-004"):
        main(["ingest", str(child), "--parent", parent])


def test_ingest_derived_with_transform(in_repo: Path, tmp_path: Path, capsys) -> None:
    src = _mk(tmp_path, "a.bin", b"root")
    assert main(["ingest", str(src)]) == 0
    parent = capsys.readouterr().out.strip()

    tf = _mk(tmp_path, "t.py", b"# transform code\n")
    child = _mk(tmp_path, "b.bin", b"derived")
    assert (
        main(
            [
                "ingest",
                str(child),
                "--parent",
                parent,
                "--transform-file",
                str(tf),
                "--params-json",
                '{"k": 1}',
            ]
        )
        == 0
    )
    nid = capsys.readouterr().out.strip()

    assert main(["verify", nid]) == 0
    assert main(["fsck"]) == 0


def test_ingest_rejects_bad_params(in_repo: Path, tmp_path: Path) -> None:
    src = _mk(tmp_path, "a.bin", b"root")
    with pytest.raises(SystemExit, match="JSON object"):
        main(["ingest", str(src), "--params-json", "[1,2]"])


def test_fsck_detects_tamper(in_repo: Path, tmp_path: Path, capsys) -> None:
    src = _mk(tmp_path, "a.bin", b"root")
    assert main(["ingest", str(src)]) == 0
    nid = capsys.readouterr().out.strip()

    obj = in_repo / "ledger" / "objects" / nid[:2] / nid
    obj.write_bytes(b"tampered")
    assert main(["fsck"]) == 2
    assert "hash" in capsys.readouterr().out
