"""Content-addressed store: ``ledger/objects/<hex[:2]>/<digest>``.

Ported from 4GARTHA ``src/ledger/cas.py`` (2ab510f). Byte identity is the
only notion of determinism at this layer.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

CHUNK_SIZE = 1024 * 1024


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(CHUNK_SIZE)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@dataclass(frozen=True)
class CasPaths:
    root: Path  # repo root
    objects_dir: Path  # root / "ledger" / "objects"

    @staticmethod
    def from_repo_root(repo_root: Path) -> "CasPaths":
        return CasPaths(
            root=repo_root,
            objects_dir=repo_root / "ledger" / "objects",
        )

    def object_path(self, digest: str) -> Path:
        # Spread by prefix to avoid huge dirs.
        prefix = digest[:2]
        return self.objects_dir / prefix / digest


def has_blob(cas: CasPaths, digest: str) -> bool:
    return cas.object_path(digest).is_file()


def store_blob(src: Path, cas: CasPaths, digest: str) -> Path:
    """Store bytes at their content address. Idempotent for identical bytes.

    Raises RuntimeError if an existing blob at this address does not hash to
    its own name (a corrupted store must never be silently extended).
    """

    dst = cas.object_path(digest)
    dst.parent.mkdir(parents=True, exist_ok=True)

    if dst.exists():
        existing = sha256_file(dst)
        if existing != digest:
            raise RuntimeError(
                f"CAS corruption: {dst} hashes to {existing}, expected {digest}"
            )
        return dst

    # Copy bytes verbatim; atomic temp -> rename to avoid partial writes.
    tmp = dst.with_suffix(".tmp")
    tmp.write_bytes(src.read_bytes())
    tmp.replace(dst)
    return dst
