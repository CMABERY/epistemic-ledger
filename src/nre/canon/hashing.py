"""P2 — Canonical bytes + deterministic hashing (frozen semantics).

Ported from 4GARTHA `canon/ids.py` (2ab510f); renamed per ADR-011 because this
module is canonical-JSON hashing, not id normalization. This layer is
policy-free: it defines *how* bytes are hashed, not *what* should be hashed.

If `canon_json_bytes` changes, every derived hash in the system becomes
invalid at once. That is intentional.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canon_json_bytes(obj: Any) -> bytes:
    """Deterministic JSON bytes.

    Encoding (Sprint-1, frozen):
      - UTF-8
      - keys sorted
      - separators without whitespace
      - ensure_ascii = False (preserve Unicode)

    ADR-010: allow_nan=False added over the shipped original — NaN/Infinity in
    canonical material would be a silent nondeterminism hazard. No frozen
    vector observes this corner.
    """

    s = json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return s.encode("utf-8")


def sha256_hex(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def sha256_prefixed(data: bytes, prefix: str = "sha256") -> str:
    """Return a stable digest string: "<prefix>:<64-hex>"."""

    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError("sha256_prefixed expects bytes-like input")
    return f"{prefix}:{sha256_hex(bytes(data))}"


def is_sha256_prefixed(s: str, prefix: str = "sha256") -> bool:
    if not isinstance(s, str):
        return False
    if not s.startswith(prefix + ":"):
        return False
    hexpart = s.split(":", 1)[1]
    if len(hexpart) != 64:
        return False
    return all(c in "0123456789abcdef" for c in hexpart)
