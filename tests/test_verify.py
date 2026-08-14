from __future__ import annotations

import json
from pathlib import Path

from ledger.cas import CasPaths, sha256_bytes, store_blob
from ledger.manifest import (
    Node,
    Transform,
    node_manifest_path,
    serialize_manifest,
    write_node_manifest,
)
from ledger.schema import ROOT_TRANSFORM_DIGEST
from ledger.verify import fsck, verify_node, verify_reachable


def _ingest_root(repo: Path, tmp: Path, content: bytes) -> str:
    src = tmp / f"src-{sha256_bytes(content)[:8]}"
    src.write_bytes(content)
    digest = sha256_bytes(content)
    store_blob(src, CasPaths.from_repo_root(repo), digest)
    write_node_manifest(
        repo,
        Node(
            id=digest,
            parents=[],
            transform=Transform(name="admission", digest=ROOT_TRANSFORM_DIGEST, params={}),
        ),
    )
    return digest


def _ingest_derived(
    repo: Path, tmp: Path, content: bytes, parents: list[str], transform_bytes: bytes
) -> str:
    cas = CasPaths.from_repo_root(repo)
    tsrc = tmp / f"t-{sha256_bytes(transform_bytes)[:8]}"
    tsrc.write_bytes(transform_bytes)
    tdigest = sha256_bytes(transform_bytes)
    store_blob(tsrc, cas, tdigest)

    src = tmp / f"d-{sha256_bytes(content)[:8]}"
    src.write_bytes(content)
    digest = sha256_bytes(content)
    store_blob(src, cas, digest)
    write_node_manifest(
        repo,
        Node(
            id=digest,
            parents=parents,
            transform=Transform(name="t", digest=tdigest, params={}),
        ),
    )
    return digest


def test_root_ok(ledger_repo: Path, tmp_path: Path) -> None:
    nid = _ingest_root(ledger_repo, tmp_path, b"root")
    r = verify_node(ledger_repo, nid)
    assert r.ok, r.errors


def test_missing_manifest(ledger_repo: Path) -> None:
    r = verify_node(ledger_repo, "f" * 64)
    assert not r.ok
    assert any("missing manifest" in e for e in r.errors)


def test_missing_object(ledger_repo: Path) -> None:
    nid = "a" * 64
    write_node_manifest(
        ledger_repo,
        Node(
            id=nid,
            parents=[],
            transform=Transform(name="admission", digest=ROOT_TRANSFORM_DIGEST, params={}),
        ),
    )
    r = verify_node(ledger_repo, nid)
    assert not r.ok
    assert any("missing object" in e for e in r.errors)


def test_object_hash_mismatch(ledger_repo: Path, tmp_path: Path) -> None:
    nid = _ingest_root(ledger_repo, tmp_path, b"root")
    obj = CasPaths.from_repo_root(ledger_repo).object_path(nid)
    obj.write_bytes(b"tampered")
    r = verify_node(ledger_repo, nid)
    assert not r.ok
    assert any("object hash mismatch" in e for e in r.errors)


def test_missing_parent(ledger_repo: Path, tmp_path: Path) -> None:
    nid = _ingest_derived(ledger_repo, tmp_path, b"child", ["b" * 64], b"# t")
    r = verify_node(ledger_repo, nid)
    assert not r.ok
    assert any("missing parent manifest" in e for e in r.errors)


def test_schema_invalid_manifest(ledger_repo: Path, tmp_path: Path) -> None:
    nid = _ingest_root(ledger_repo, tmp_path, b"root")
    mp = node_manifest_path(ledger_repo, nid)
    m = json.loads(mp.read_text())
    m["unexpected"] = True
    mp.write_text(serialize_manifest(m))
    r = verify_node(ledger_repo, nid)
    assert not r.ok
    assert any(e.startswith("schema") for e in r.errors)


def test_derived_without_cas_transform(ledger_repo: Path, tmp_path: Path) -> None:
    parent = _ingest_root(ledger_repo, tmp_path, b"root")
    nid = _ingest_derived(ledger_repo, tmp_path, b"child", [parent], b"# t")
    # Remove the transform blob from the CAS.
    m = json.loads(node_manifest_path(ledger_repo, nid).read_text())
    tdigest = m["transform"]["digest"]
    CasPaths.from_repo_root(ledger_repo).object_path(tdigest).unlink()
    r = verify_node(ledger_repo, nid)
    assert not r.ok
    assert any("transform not in CAS" in e for e in r.errors)


def test_tampered_transform_fails_all_layers(ledger_repo: Path, tmp_path: Path) -> None:
    parent = _ingest_root(ledger_repo, tmp_path, b"root")
    nid = _ingest_derived(ledger_repo, tmp_path, b"child", [parent], b"# t")
    m = json.loads(node_manifest_path(ledger_repo, nid).read_text())
    tdigest = m["transform"]["digest"]
    # Overwrite the transform blob in place: same path, different bytes.
    CasPaths.from_repo_root(ledger_repo).object_path(tdigest).write_bytes(b"# evil")

    r = verify_node(ledger_repo, nid)
    assert not r.ok
    assert any("transform object corrupt" in e for e in r.errors)
    assert not verify_reachable(ledger_repo, nid).ok
    assert not fsck(ledger_repo).ok


def test_diamond_dag_reachable(ledger_repo: Path, tmp_path: Path) -> None:
    a = _ingest_root(ledger_repo, tmp_path, b"A")
    b = _ingest_derived(ledger_repo, tmp_path, b"B", [a], b"# tb")
    c = _ingest_derived(ledger_repo, tmp_path, b"C", [a], b"# tc")
    d = _ingest_derived(ledger_repo, tmp_path, b"D", [b, c], b"# td")
    r = verify_reachable(ledger_repo, d)
    assert r.ok, r.errors


def test_cycle_terminates(ledger_repo: Path, tmp_path: Path) -> None:
    # Hand-write two manifests that reference each other (cannot be produced
    # by ingest, since content addressing forbids cycles in practice).
    x, y = "1" * 64, "2" * 64
    for nid, parent in ((x, y), (y, x)):
        write_node_manifest(
            ledger_repo,
            Node(
                id=nid,
                parents=[parent],
                transform=Transform(name="t", digest="3" * 64, params={}),
            ),
        )
    r = verify_reachable(ledger_repo, x)
    assert not r.ok  # objects missing etc., but it must terminate


def test_fsck_clean_and_detects_all(ledger_repo: Path, tmp_path: Path) -> None:
    a = _ingest_root(ledger_repo, tmp_path, b"A")
    b = _ingest_derived(ledger_repo, tmp_path, b"B", [a], b"# tb")

    from ledger.refs import set_ref

    set_ref(ledger_repo, "main", b)
    r = fsck(ledger_repo)
    assert r.ok, r.errors

    # 1) corrupt an object
    obj = CasPaths.from_repo_root(ledger_repo).object_path(a)
    obj.write_bytes(b"junk")
    # 2) stray file in nodes/
    (ledger_repo / "ledger" / "nodes" / "stray.txt").write_text("x")
    # 3) dangling ref
    (ledger_repo / "ledger" / "refs" / "dangling").write_text("9" * 64 + "\n")

    r2 = fsck(ledger_repo)
    assert not r2.ok
    joined = "\n".join(r2.errors)
    assert "object corrupt" in joined or "object hash mismatch" in joined
    assert "stray file in nodes/" in joined
    assert "dangling" in joined
