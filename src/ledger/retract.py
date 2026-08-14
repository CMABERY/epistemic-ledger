"""Retraction records: append-only epistemic status, never deletion (ADR-013).

A retraction marks a node as no longer endorsed — wrong, poisoned, or
superseded — without touching the node itself. The record lives at
``ledger/retractions/<node_id>.json`` (protected add-only prefix), is
immutable once created, and optionally names a successor node.

Supersession = point refs at the successor. Deletion does not exist at this
layer; the only true-deletion path is the break-glass ceremony in
``docs/RETRACTION.md``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from jsonschema import Draft202012Validator

from ledger.manifest import node_manifest_path, serialize_manifest


def retraction_path(repo_root: Path, node_id: str) -> Path:
    return repo_root / "ledger" / "retractions" / f"{node_id}.json"


def _load_retraction_schema(repo_root: Path) -> Dict[str, Any]:
    p = repo_root / "ledger" / "schema" / "retraction.schema.json"
    return json.loads(p.read_text(encoding="utf-8"))


def validate_retraction(repo_root: Path, obj: Any) -> List[str]:
    v = Draft202012Validator(_load_retraction_schema(repo_root))
    errs = sorted(
        (str(list(e.path)), str(e.message)) for e in v.iter_errors(obj)
    )
    return [f"retraction schema: {msg}" for _path, msg in errs]


@dataclass(frozen=True)
class Retraction:
    retracts: str
    reason: str
    superseded_by: str | None
    created: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "retracts": self.retracts,
            "reason": self.reason,
            "superseded_by": self.superseded_by,
            "created": self.created,
        }


def is_retracted(repo_root: Path, node_id: str) -> bool:
    return retraction_path(repo_root, node_id).is_file()


def read_retraction(repo_root: Path, node_id: str) -> Dict[str, Any]:
    p = retraction_path(repo_root, node_id)
    return json.loads(p.read_text(encoding="utf-8"))


def write_retraction(
    repo_root: Path,
    node_id: str,
    reason: str,
    superseded_by: str | None = None,
    created: str | None = None,
) -> Path:
    """Create the (single, immutable) retraction record for a node."""

    if not node_manifest_path(repo_root, node_id).is_file():
        raise FileNotFoundError(f"cannot retract unknown node: {node_id}")
    if superseded_by is not None and not node_manifest_path(
        repo_root, superseded_by
    ).is_file():
        raise FileNotFoundError(
            f"successor manifest does not exist: {superseded_by}"
        )

    record = Retraction(
        retracts=node_id,
        reason=reason,
        superseded_by=superseded_by,
        created=created
        or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    ).to_dict()

    errors = validate_retraction(repo_root, record)
    if errors:
        raise ValueError("; ".join(errors))

    p = retraction_path(repo_root, node_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    txt = serialize_manifest(record)
    try:
        # Append-only: one retraction per node, immutable once created.
        with p.open("x", encoding="utf-8") as f:
            f.write(txt)
    except FileExistsError:
        raise FileExistsError(f"node already retracted: {p}") from None
    return p
