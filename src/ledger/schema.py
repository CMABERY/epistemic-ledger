"""Pinned node-manifest schema: interpretation is gated.

A manifest is not "a node" unless it validates against the pinned schema
(``ledger/schema/node.schema.json``, sha256 pinned in ``NODE_SCHEMA_SHA256``).
New over the original kernel: the original never schema-validated manifests.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from jsonschema import Draft202012Validator

# ADR-005: sentinel transform digest for root/admission nodes = sha256 of
# empty bytes. The pinned schema requires `transform` on every node; roots
# have no derivation to replay.
ROOT_TRANSFORM_DIGEST = (
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
)


def load_node_schema(repo_root: Path) -> Tuple[Dict[str, Any], str]:
    schema_path = repo_root / "ledger" / "schema" / "node.schema.json"
    pin_path = repo_root / "ledger" / "schema" / "NODE_SCHEMA_SHA256"

    schema_bytes = schema_path.read_bytes()
    schema_sha = hashlib.sha256(schema_bytes).hexdigest()

    pinned = pin_path.read_text(encoding="utf-8").strip()
    if pinned != schema_sha:
        raise RuntimeError(
            "node schema hash pin mismatch\n"
            f"  pinned:  {pinned}\n"
            f"  actual:  {schema_sha}\n"
            f"  schema:  {schema_path}"
        )

    return json.loads(schema_bytes.decode("utf-8")), schema_sha


def _pointer(parts: Any) -> str:
    try:
        seq = list(parts)
    except Exception:
        seq = []

    def esc(p: Any) -> str:
        return str(p).replace("~", "~0").replace("/", "~1")

    return "" if not seq else "/" + "/".join(esc(p) for p in seq)


def validate_manifest(repo_root: Path, obj: Any) -> List[str]:
    """Validate a manifest object. Returns deterministic error strings."""

    schema, _ = load_node_schema(repo_root)
    v = Draft202012Validator(schema)
    errs = [
        (_pointer(e.path), str(e.validator), str(e.message)) for e in v.iter_errors(obj)
    ]
    errs.sort()
    return [f"schema{path or '/'}: {message}" for path, _validator, message in errs]
