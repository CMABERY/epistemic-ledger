from __future__ import annotations

from pathlib import Path

import pytest

from ledger.manifest import Node, Transform, write_node_manifest
from ledger.refs import get_ref, ref_path, resolve, set_ref
from ledger.schema import ROOT_TRANSFORM_DIGEST

H = "a" * 64


def _write_node(repo: Path, nid: str = H) -> None:
    write_node_manifest(
        repo,
        Node(
            id=nid,
            parents=[],
            transform=Transform(name="admission", digest=ROOT_TRANSFORM_DIGEST, params={}),
        ),
    )


def test_set_get_roundtrip(ledger_repo: Path) -> None:
    _write_node(ledger_repo)
    set_ref(ledger_repo, "main", H)
    assert get_ref(ledger_repo, "main") == H
    assert resolve(ledger_repo, "main") == H
    assert resolve(ledger_repo, H) == H


def test_set_refuses_dangling(ledger_repo: Path) -> None:
    with pytest.raises(FileNotFoundError, match="refusing to set ref"):
        set_ref(ledger_repo, "main", "b" * 64)


def test_set_refuses_bad_id(ledger_repo: Path) -> None:
    with pytest.raises(ValueError):
        set_ref(ledger_repo, "main", "nonsense")


def test_bad_ref_names_rejected(ledger_repo: Path) -> None:
    for bad in ("../escape", ".hidden", "a/b", "", ".keep"):
        with pytest.raises(ValueError):
            ref_path(ledger_repo, bad)


def test_get_missing_ref(ledger_repo: Path) -> None:
    with pytest.raises(FileNotFoundError):
        get_ref(ledger_repo, "nope")
