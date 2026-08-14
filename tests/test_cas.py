from __future__ import annotations

from pathlib import Path

import pytest

from ledger.cas import CasPaths, has_blob, sha256_bytes, sha256_file, store_blob


def test_store_and_shard(ledger_repo: Path, tmp_path: Path) -> None:
    src = tmp_path / "artifact.bin"
    src.write_bytes(b"hello ledger")
    digest = sha256_file(src)
    assert digest == sha256_bytes(b"hello ledger")

    cas = CasPaths.from_repo_root(ledger_repo)
    dst = store_blob(src, cas, digest)
    assert dst == ledger_repo / "ledger" / "objects" / digest[:2] / digest
    assert dst.read_bytes() == b"hello ledger"
    assert has_blob(cas, digest)


def test_store_idempotent(ledger_repo: Path, tmp_path: Path) -> None:
    src = tmp_path / "a"
    src.write_bytes(b"x")
    cas = CasPaths.from_repo_root(ledger_repo)
    digest = sha256_file(src)
    p1 = store_blob(src, cas, digest)
    p2 = store_blob(src, cas, digest)
    assert p1 == p2


def test_store_detects_corrupt_existing(ledger_repo: Path, tmp_path: Path) -> None:
    src = tmp_path / "a"
    src.write_bytes(b"x")
    cas = CasPaths.from_repo_root(ledger_repo)
    digest = sha256_file(src)
    dst = store_blob(src, cas, digest)
    dst.write_bytes(b"corrupted")
    with pytest.raises(RuntimeError, match="CAS corruption"):
        store_blob(src, cas, digest)
