"""Sprint-1 — Pre-Δ verifier engine (frozen fencepost semantics).

Ported from 4GARTHA `verify/verify.py` (2ab510f). Deliberately narrow:
schema-first validation plus two circuit-breaker failure modes.

Frozen behaviors:
  - Schema-first validation using the pinned Draft 2020-12 validator.
  - Deterministic hashing bytes: canon_json_bytes + sha256_prefixed.
  - Envelope exit codes: 0 OK, 10 WSS_HASH_INTEGRITY_FAILED,
    11 DSS_REQUIRES_NON_NULL_HASH, 12 SCHEMA_VALIDATION_FAILED (ADR-006).
  - Deterministic schema-error ordering:
    (doc, path, validator, message, schema_path).

Non-goals: no Notion I/O, no operator execution, no planning/Δ,
no cryptography, no schema changes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

from jsonschema import Draft202012Validator

from nre.canon.hashing import canon_json_bytes, sha256_prefixed
from nre.exit_codes import (
    EXIT_DSS_REQUIRES_NON_NULL_HASH,
    EXIT_OK,
    EXIT_SCHEMA_VALIDATION_FAILED,
    EXIT_WSS_HASH_INTEGRITY_FAILED,
)


@dataclass(frozen=True)
class VerifyEnvelope:
    ok: bool
    exit_code: int
    schema_sha256: str
    schema_errors: List[Dict[str, Any]]
    errors: List[str]
    computed: Dict[str, Any]

    def to_json(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "exit_code": self.exit_code,
            "schema_sha256": self.schema_sha256,
            "schema_errors": list(self.schema_errors),
            "errors": list(self.errors),
            "computed": dict(self.computed),
        }


def _sha256_hex(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()


def _json_pointer(path_parts: Any) -> str:
    # jsonschema error.path / error.schema_path are deques of keys/indices.
    try:
        parts = list(path_parts)
    except Exception:
        parts = []

    def esc(p: Any) -> str:
        s = str(p)
        return s.replace("~", "~0").replace("/", "~1")

    return "" if not parts else "/" + "/".join(esc(p) for p in parts)


def _sorted_schema_errors(errors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def k(e: Dict[str, Any]) -> Tuple[str, str, str, str, str]:
        return (
            str(e.get("doc", "")),
            str(e.get("path", "")),
            str(e.get("validator", "")),
            str(e.get("message", "")),
            str(e.get("schema_path", "")),
        )

    return sorted(errors, key=k)


def _load_schema(repo_root: Path) -> Tuple[Dict[str, Any], str]:
    schema_path = repo_root / "schemas" / "nre-artifacts-v1.0.2.schema.json"
    sha_path = repo_root / "schemas" / "SCHEMA_SHA256"

    schema_bytes = schema_path.read_bytes()
    schema_sha = _sha256_hex(schema_bytes)

    pinned = sha_path.read_text(encoding="utf-8").strip()
    if pinned != schema_sha:
        raise RuntimeError(
            "schema hash pin mismatch\n"
            f"  pinned:  {pinned}\n"
            f"  actual:  {schema_sha}\n"
            f"  schema:  {schema_path}"
        )

    schema = json.loads(schema_bytes.decode("utf-8"))
    return schema, schema_sha


def _subschema(base: Dict[str, Any], def_name: str) -> Dict[str, Any]:
    defs = base.get("$defs", {})
    if def_name not in defs:
        raise KeyError(f"schema missing $defs/{def_name}")
    # Wrap the definition so $ref targets (#/$defs/...) remain resolvable.
    d = defs[def_name]
    return {
        "$schema": base.get("$schema"),
        "$defs": defs,
        **d,
    }


def _validate_doc(
    doc: str, instance: Any, validator: Draft202012Validator
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for err in validator.iter_errors(instance):
        out.append(
            {
                "doc": doc,
                "path": _json_pointer(err.path),
                "schema_path": _json_pointer(err.schema_path),
                "validator": str(err.validator),
                "message": str(err.message),
            }
        )
    return out


def verify_triplet(repo_root: Path, cap: Any, wss: Any, dss: Any) -> VerifyEnvelope:
    base_schema, schema_sha = _load_schema(repo_root)

    schema_errors: List[Dict[str, Any]] = []
    cap_v = Draft202012Validator(_subschema(base_schema, "CAP"))
    wss_v = Draft202012Validator(_subschema(base_schema, "WSS"))
    dss_v = Draft202012Validator(_subschema(base_schema, "DSS"))

    schema_errors.extend(_validate_doc("cap", cap, cap_v))
    schema_errors.extend(_validate_doc("wss", wss, wss_v))
    schema_errors.extend(_validate_doc("dss", dss, dss_v))
    schema_errors = _sorted_schema_errors(schema_errors)

    computed: Dict[str, Any] = {}
    errors: List[str] = []

    # Schema-first: do not continue if schema fails.
    if schema_errors:
        errors.append("SCHEMA_VALIDATION_FAILED")
        return VerifyEnvelope(
            ok=False,
            exit_code=EXIT_SCHEMA_VALIDATION_FAILED,
            schema_sha256=schema_sha,
            schema_errors=schema_errors,
            errors=errors,
            computed=computed,
        )

    # ---- WSS integrity (frozen circuit breaker) ----
    computed_wss = sha256_prefixed(canon_json_bytes(wss.get("payload")))
    computed["wss_payload_hash"] = computed_wss

    if wss.get("hash") != computed_wss:
        errors.append("WSS_HASH_INTEGRITY_FAILED")
        computed["wss_payload_hash_expected"] = wss.get("hash")
        return VerifyEnvelope(
            ok=False,
            exit_code=EXIT_WSS_HASH_INTEGRITY_FAILED,
            schema_sha256=schema_sha,
            schema_errors=schema_errors,
            errors=errors,
            computed=computed,
        )

    # ---- DSS obligation (frozen circuit breaker) ----
    if bool(dss.get("requires_non_null_hash")) and dss.get("hash") is None:
        errors.append("DSS_REQUIRES_NON_NULL_HASH")
        return VerifyEnvelope(
            ok=False,
            exit_code=EXIT_DSS_REQUIRES_NON_NULL_HASH,
            schema_sha256=schema_sha,
            schema_errors=schema_errors,
            errors=errors,
            computed=computed,
        )

    return VerifyEnvelope(
        ok=True,
        exit_code=EXIT_OK,
        schema_sha256=schema_sha,
        schema_errors=schema_errors,
        errors=errors,
        computed=computed,
    )
