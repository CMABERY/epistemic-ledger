"""End-to-end replay: ingest roots, derive a child, reproduce its bytes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ledger.cli import main
from ledger.replay import replay_node

TRANSFORMS = Path(__file__).resolve().parents[1] / "transforms"


@pytest.fixture
def in_repo(ledger_repo: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(ledger_repo)
    return ledger_repo


def _ingest_file(tmp_path: Path, name: str, content: bytes, capsys, *extra: str) -> str:
    p = tmp_path / name
    p.write_bytes(content)
    assert main(["ingest", str(p), *extra]) == 0
    return capsys.readouterr().out.strip()


def _derive_concat(
    in_repo: Path, tmp_path: Path, capsys, suffix: str = "!"
) -> tuple[str, str, str]:
    """Ingest two roots and a genuinely derived concat child. Returns ids."""

    a = _ingest_file(tmp_path, "a.bin", b"alpha-", capsys)
    b = _ingest_file(tmp_path, "b.bin", b"beta", capsys)
    child_bytes = b"alpha-" + b"beta" + suffix.encode("utf-8")
    child = _ingest_file(
        tmp_path,
        "c.bin",
        child_bytes,
        capsys,
        "--parent",
        a,
        "--parent",
        b,
        "--transform-file",
        str(TRANSFORMS / "concat_parents.py"),
        "--params-json",
        json.dumps({"suffix": suffix}),
        "--runner=python3",
        "--runner=-I",  # '=' form: argparse would otherwise read -I as a flag
    )
    return a, b, child


def test_replay_reproduces_child(in_repo: Path, tmp_path: Path, capsys) -> None:
    _, _, child = _derive_concat(in_repo, tmp_path, capsys)
    r = replay_node(in_repo, child)
    assert r.ok, r.errors
    assert r.output_digest == child


def test_replay_cli_and_verify_replay(in_repo: Path, tmp_path: Path, capsys) -> None:
    _, _, child = _derive_concat(in_repo, tmp_path, capsys)
    assert main(["replay", child]) == 0
    assert main(["verify", child, "--replay"]) == 0
    assert main(["refs", "set", "main", child]) == 0
    assert main(["verify-reachable", "--replay"]) == 0
    assert main(["fsck", "--replay"]) == 0


def test_replay_root_trivial(in_repo: Path, tmp_path: Path, capsys) -> None:
    a = _ingest_file(tmp_path, "a.bin", b"root", capsys)
    r = replay_node(in_repo, a)
    assert r.ok
    assert r.output_digest == a


def test_replay_detects_wrong_derivation(in_repo: Path, tmp_path: Path, capsys) -> None:
    a = _ingest_file(tmp_path, "a.bin", b"alpha-", capsys)
    # Claimed child bytes do NOT equal concat(parents) + suffix.
    child = _ingest_file(
        tmp_path,
        "c.bin",
        b"unrelated bytes",
        capsys,
        "--parent",
        a,
        "--transform-file",
        str(TRANSFORMS / "concat_parents.py"),
        "--params-json",
        '{"suffix": "!"}',
    )
    r = replay_node(in_repo, child)
    assert not r.ok
    assert any("derivation mismatch" in e for e in r.errors)


def test_replay_missing_transform_blob(in_repo: Path, tmp_path: Path, capsys) -> None:
    _, _, child = _derive_concat(in_repo, tmp_path, capsys)
    m = json.loads((in_repo / "ledger" / "nodes" / f"{child}.json").read_text())
    tdigest = m["transform"]["digest"]
    (in_repo / "ledger" / "objects" / tdigest[:2] / tdigest).unlink()
    r = replay_node(in_repo, child)
    assert not r.ok
    assert any("missing transform definition in CAS" in e for e in r.errors)


def test_replay_keep_workdir(in_repo: Path, tmp_path: Path, capsys) -> None:
    _, _, child = _derive_concat(in_repo, tmp_path, capsys)
    wd = tmp_path / "replay-wd"
    r = replay_node(in_repo, child, workdir=wd, keep=True)
    assert r.ok, r.errors
    assert (wd / "out.bin").is_file()
    assert (wd / "parents.json").is_file()
    parents_manifest = json.loads((wd / "parents.json").read_text())
    assert [p["index"] for p in parents_manifest] == [0, 1]
