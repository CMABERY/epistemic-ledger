"""Mutable convenience refs: ``ledger/refs/<name>`` -> node id.

Refs are the only intentionally mutable write surface of the ledger.
Immutability is provided by content-addressed objects/nodes, never by refs.

Additive strictness over the original: a ref may only be set to a node whose
manifest exists (the original allowed dangling refs — a recorded gap).
"""

from __future__ import annotations

import re
from pathlib import Path

from ledger.manifest import node_manifest_path

HEX64 = re.compile(r"^[0-9a-f]{64}$")
REF_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def ref_path(repo_root: Path, name: str) -> Path:
    if not REF_NAME.match(name) or name == ".keep":
        raise ValueError(f"invalid ref name: {name!r}")
    return repo_root / "ledger" / "refs" / name


def set_ref(repo_root: Path, name: str, node_id: str) -> Path:
    if not HEX64.match(node_id):
        raise ValueError(f"invalid node id: {node_id!r}")
    if not node_manifest_path(repo_root, node_id).is_file():
        raise FileNotFoundError(
            f"refusing to set ref {name!r}: no manifest for node {node_id}"
        )
    p = ref_path(repo_root, name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(node_id + "\n", encoding="utf-8")
    return p


def get_ref(repo_root: Path, name: str) -> str:
    p = ref_path(repo_root, name)
    if not p.is_file():
        raise FileNotFoundError(f"missing ref: {p}")
    value = p.read_text(encoding="utf-8").strip()
    if not HEX64.match(value):
        raise ValueError(f"ref {name!r} does not contain a node id: {value!r}")
    return value


def resolve(repo_root: Path, name_or_id: str) -> str:
    """Resolve a 64-hex node id (passthrough) or a ref name."""

    if HEX64.match(name_or_id):
        return name_or_id
    return get_ref(repo_root, name_or_id)
