"""Every byte of the frozen surface is pinned (ADR-014)."""

from __future__ import annotations

import hashlib
from pathlib import Path


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_frozen_sums_all_match(repo_root: Path) -> None:
    sums = (repo_root / "fixtures" / "FROZEN_SHA256SUMS").read_text(encoding="utf-8")
    lines = [ln for ln in sums.splitlines() if ln.strip()]
    assert len(lines) == 28
    for line in lines:
        digest, path = line.split(maxsplit=1)
        assert _sha256(repo_root / path.strip()) == digest, path


def test_node_schema_pin(repo_root: Path) -> None:
    pinned = (repo_root / "ledger" / "schema" / "NODE_SCHEMA_SHA256").read_text().strip()
    assert _sha256(repo_root / "ledger" / "schema" / "node.schema.json") == pinned
    assert pinned == "900af7e40b84dcaf845630bbf164fc386feeb75bbeb7b27d9cc4e2cd1a77c266"


def test_nre_schema_pin(repo_root: Path) -> None:
    pinned = (repo_root / "schemas" / "SCHEMA_SHA256").read_text().strip()
    assert _sha256(repo_root / "schemas" / "nre-artifacts-v1.0.2.schema.json") == pinned
