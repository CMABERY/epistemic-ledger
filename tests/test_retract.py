"""Retraction records (ADR-013): append-only epistemic status, never deletion."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ledger.cli import main
from ledger.manifest import Node, Transform, write_node_manifest
from ledger.retract import is_retracted, read_retraction, write_retraction
from ledger.schema import ROOT_TRANSFORM_DIGEST
from ledger.verify import fsck, verify_node


def _mk_node(repo: Path, nid: str) -> None:
    write_node_manifest(
        repo,
        Node(
            id=nid,
            parents=[],
            transform=Transform(name="admission", digest=ROOT_TRANSFORM_DIGEST, params={}),
        ),
    )


A = "a" * 64
B = "b" * 64


def test_write_and_read(ledger_repo: Path) -> None:
    _mk_node(ledger_repo, A)
    _mk_node(ledger_repo, B)
    p = write_retraction(ledger_repo, A, "bad input data", superseded_by=B)
    assert p.name == f"{A}.json"
    assert is_retracted(ledger_repo, A)
    rec = read_retraction(ledger_repo, A)
    assert rec["retracts"] == A
    assert rec["superseded_by"] == B
    assert rec["reason"] == "bad input data"


def test_retraction_immutable(ledger_repo: Path) -> None:
    _mk_node(ledger_repo, A)
    write_retraction(ledger_repo, A, "first")
    with pytest.raises(FileExistsError, match="already retracted"):
        write_retraction(ledger_repo, A, "second")


def test_retract_unknown_node_fails(ledger_repo: Path) -> None:
    with pytest.raises(FileNotFoundError, match="unknown node"):
        write_retraction(ledger_repo, A, "nope")


def test_dangling_successor_fails(ledger_repo: Path) -> None:
    _mk_node(ledger_repo, A)
    with pytest.raises(FileNotFoundError, match="successor manifest"):
        write_retraction(ledger_repo, A, "reason", superseded_by=B)


def test_empty_reason_rejected(ledger_repo: Path) -> None:
    _mk_node(ledger_repo, A)
    with pytest.raises(ValueError, match="retraction schema"):
        write_retraction(ledger_repo, A, "")


def test_verify_warns_then_denies(ledger_repo: Path, tmp_path: Path) -> None:
    # Full node (object present) so only retraction status is at play.
    src = tmp_path / "a.bin"
    src.write_bytes(b"content")
    from ledger.cas import CasPaths, sha256_file, store_blob

    nid = sha256_file(src)
    store_blob(src, CasPaths.from_repo_root(ledger_repo), nid)
    _mk_node(ledger_repo, nid)

    assert verify_node(ledger_repo, nid).ok
    write_retraction(ledger_repo, nid, "superseded by better derivation")

    r = verify_node(ledger_repo, nid)
    assert r.ok  # warning only
    assert any("retracted" in w for w in r.warnings)

    r2 = verify_node(ledger_repo, nid, deny_retracted=True)
    assert not r2.ok
    assert any("retracted" in e for e in r2.errors)


def test_fsck_audits_retractions(ledger_repo: Path, tmp_path: Path) -> None:
    from ledger.cas import CasPaths, sha256_file, store_blob

    src = tmp_path / "real.bin"
    src.write_bytes(b"real artifact")
    nid = sha256_file(src)
    store_blob(src, CasPaths.from_repo_root(ledger_repo), nid)
    _mk_node(ledger_repo, nid)
    write_retraction(ledger_repo, nid, "reason")
    assert fsck(ledger_repo).ok

    # Corrupt: retracts field mismatch + stray file
    bad = ledger_repo / "ledger" / "retractions" / (B + ".json")
    bad.write_text(
        json.dumps(
            {
                "retracts": A,
                "reason": "x",
                "superseded_by": None,
                "created": "2026-08-13T00:00:00Z",
            }
        )
    )
    (ledger_repo / "ledger" / "retractions" / "stray.txt").write_text("x")
    r = fsck(ledger_repo)
    assert not r.ok
    joined = "\n".join(r.errors)
    assert "retracts field mismatch" in joined
    assert "stray file in retractions/" in joined


def test_cli_retract_flow(ledger_repo: Path, tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(ledger_repo)
    src = tmp_path / "a.bin"
    src.write_bytes(b"artifact")
    assert main(["ingest", str(src)]) == 0
    nid = capsys.readouterr().out.strip()

    assert main(["retract", nid, "--reason", "test retraction"]) == 0
    capsys.readouterr()

    assert main(["verify", nid]) == 0
    out = capsys.readouterr().out
    assert "warning: retracted" in out
    assert "OK" in out

    assert main(["verify", nid, "--deny-retracted"]) == 2

    with pytest.raises(SystemExit, match="already retracted"):
        main(["retract", nid, "--reason", "again"])
