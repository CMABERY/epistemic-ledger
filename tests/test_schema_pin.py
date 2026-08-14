from __future__ import annotations

from pathlib import Path

import pytest

from ledger.schema import ROOT_TRANSFORM_DIGEST, load_node_schema, validate_manifest


def _valid_manifest() -> dict:
    h = "a" * 64
    return {
        "id": h,
        "parents": [],
        "transform": {"name": "t", "digest": h, "params": {}},
    }


def test_load_ok(ledger_repo: Path) -> None:
    schema, sha = load_node_schema(ledger_repo)
    assert schema["title"] == "Epistemic Ledger Node Manifest"
    assert sha == "900af7e40b84dcaf845630bbf164fc386feeb75bbeb7b27d9cc4e2cd1a77c266"


def test_pin_mismatch_raises(ledger_repo: Path) -> None:
    (ledger_repo / "ledger" / "schema" / "NODE_SCHEMA_SHA256").write_text("0" * 64 + "\n")
    with pytest.raises(RuntimeError, match="pin mismatch"):
        load_node_schema(ledger_repo)


def test_valid_manifest_passes(ledger_repo: Path) -> None:
    assert validate_manifest(ledger_repo, _valid_manifest()) == []


def test_invalid_manifests_rejected(ledger_repo: Path) -> None:
    m = _valid_manifest()
    del m["transform"]
    assert any("transform" in e for e in validate_manifest(ledger_repo, m))

    m2 = _valid_manifest()
    m2["id"] = "not-hex"
    assert validate_manifest(ledger_repo, m2)

    m3 = _valid_manifest()
    m3["extra"] = 1  # additionalProperties: false
    assert validate_manifest(ledger_repo, m3)

    m4 = _valid_manifest()
    m4["transform"]["runner"] = []  # minItems: 1
    assert validate_manifest(ledger_repo, m4)


def test_root_sentinel_is_sha256_of_empty() -> None:
    import hashlib

    assert ROOT_TRANSFORM_DIGEST == hashlib.sha256(b"").hexdigest()
