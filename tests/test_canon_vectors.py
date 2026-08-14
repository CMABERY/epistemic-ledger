"""canon-v1 primitives against the frozen vectors, plus authored edge cases."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nre.canon.fileref import file_ref
from nre.canon.hashing import canon_json_bytes, is_sha256_prefixed, sha256_prefixed
from nre.canon.strings import normalize_string


def _vectors(repo_root: Path, name: str) -> list[dict]:
    p = repo_root / "fixtures" / "vectors" / name
    return json.loads(p.read_text(encoding="utf-8"))["tests"]


def test_strings_vectors(repo_root: Path) -> None:
    tests = _vectors(repo_root, "strings.json")
    assert tests, "frozen vector file must not be empty"
    for t in tests:
        assert normalize_string(t["in"]) == t["expect"]


def test_ids_vectors(repo_root: Path) -> None:
    tests = _vectors(repo_root, "ids.json")
    assert tests
    for t in tests:
        assert sha256_prefixed(canon_json_bytes(t["obj"])) == t["expect"]


def test_fileref_vectors(repo_root: Path) -> None:
    vectors_dir = repo_root / "fixtures" / "vectors"
    tests = _vectors(repo_root, "fileref.json")
    assert tests
    for t in tests:
        assert file_ref(vectors_dir / t["path"]).raw_sha256 == t["expect"]


# ---- Authored edges (not frozen) ----


def test_normalize_string_rejects_non_str() -> None:
    with pytest.raises(TypeError):
        normalize_string(42)  # type: ignore[arg-type]


def test_canon_json_bytes_rejects_nan() -> None:
    # ADR-010: allow_nan=False added deliberately over the shipped original.
    with pytest.raises(ValueError):
        canon_json_bytes(float("nan"))


def test_canon_json_bytes_preserves_unicode_and_sorts_keys() -> None:
    assert canon_json_bytes({"b": "é", "a": 1}) == '{"a":1,"b":"é"}'.encode("utf-8")


def test_sha256_prefixed_rejects_non_bytes() -> None:
    with pytest.raises(TypeError):
        sha256_prefixed("not-bytes")  # type: ignore[arg-type]


def test_is_sha256_prefixed() -> None:
    assert is_sha256_prefixed("sha256:" + "0" * 64)
    assert not is_sha256_prefixed("sha256:" + "0" * 63)
    assert not is_sha256_prefixed("md5:" + "0" * 64)
    assert not is_sha256_prefixed("sha256:" + "Z" * 64)
    assert not is_sha256_prefixed(123)  # type: ignore[arg-type]
