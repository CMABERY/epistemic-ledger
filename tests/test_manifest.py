from __future__ import annotations

import json
from pathlib import Path

import pytest

from ledger.manifest import (
    Node,
    Transform,
    node_manifest_path,
    read_node_manifest,
    write_node_manifest,
)

H = "a" * 64


def _node(node_id: str = H) -> Node:
    return Node(
        id=node_id,
        parents=[],
        transform=Transform(name="t", digest="b" * 64, params={}),
    )


def test_write_read_roundtrip(ledger_repo: Path) -> None:
    write_node_manifest(ledger_repo, _node())
    m = read_node_manifest(ledger_repo, H)
    assert m["id"] == H
    assert m["parents"] == []
    assert m["transform"] == {"name": "t", "digest": "b" * 64, "params": {}}


def test_manifest_immutable(ledger_repo: Path) -> None:
    write_node_manifest(ledger_repo, _node())
    with pytest.raises(FileExistsError):
        write_node_manifest(ledger_repo, _node())


def test_serialization_byte_exact(ledger_repo: Path) -> None:
    node = _node()
    p = write_node_manifest(ledger_repo, node)
    expected = json.dumps(node.to_dict(), indent=2, sort_keys=True) + "\n"
    assert p.read_text(encoding="utf-8") == expected
    assert p == node_manifest_path(ledger_repo, H)


def test_optional_fields_serialized_only_when_present(ledger_repo: Path) -> None:
    node = Node(
        id="c" * 64,
        parents=[],
        transform=Transform(
            name="t",
            digest="b" * 64,
            params={},
            runner=["python3", "-I"],
            env_digest="d" * 64,
        ),
        meta={"note": "hello"},
    )
    d = node.to_dict()
    assert d["transform"]["runner"] == ["python3", "-I"]
    assert d["transform"]["env_digest"] == "d" * 64
    assert d["meta"] == {"note": "hello"}

    bare = _node().to_dict()
    assert "runner" not in bare["transform"]
    assert "env_digest" not in bare["transform"]
    assert "meta" not in bare
