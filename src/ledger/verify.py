"""Node verification: manifest validity, object integrity, parent reachability.

Ported from 4GARTHA ``src/ledger/verify.py`` (2ab510f) with deliberate
additions:
  - manifests are schema-validated against the pinned node schema (new;
    the original never validated),
  - derived nodes must have a CAS-resident transform (ADR-004),
  - ``fsck``: whole-store audit including valid-but-unreachable manifests.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Set

from ledger.cas import CasPaths, sha256_file
from ledger.manifest import node_manifest_path, read_node_manifest
from ledger.retract import is_retracted, read_retraction, validate_retraction
from ledger.schema import validate_manifest

HEX64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    errors: List[str]
    warnings: List[str] = field(default_factory=list)


def verify_node(
    repo_root: Path,
    node_id: str,
    replay: bool = False,
    deny_retracted: bool = False,
) -> VerifyResult:
    errors: List[str] = []
    warnings: List[str] = []

    # 1) manifest exists
    mp = node_manifest_path(repo_root, node_id)
    if not mp.exists():
        return VerifyResult(False, [f"missing manifest: {mp}"])

    # 2) manifest parses and validates against the pinned schema
    try:
        m = read_node_manifest(repo_root, node_id)
    except Exception as e:
        return VerifyResult(False, [f"unreadable manifest: {mp}: {e}"])

    errors.extend(validate_manifest(repo_root, m))

    if isinstance(m, dict) and m.get("id") != node_id:
        errors.append(f"manifest id mismatch: file {node_id}, id {m.get('id')!r}")

    # 3) object exists and hash matches
    cas = CasPaths.from_repo_root(repo_root)
    obj = cas.object_path(node_id)
    if not obj.exists():
        errors.append(f"missing object: {obj}")
    else:
        digest = sha256_file(obj)
        if digest != node_id:
            errors.append(f"object hash mismatch: expected {node_id}, got {digest}")

    # 4) parents reachable (manifest exists)
    parents = m.get("parents", []) if isinstance(m, dict) else []
    if not isinstance(parents, list):
        parents = []

    for p in parents:
        if not isinstance(p, str) or not HEX64.match(p):
            # Already reported by schema validation; skip lookup.
            continue
        pm = node_manifest_path(repo_root, p)
        if not pm.exists():
            errors.append(f"missing parent manifest: {pm}")

    # 5) derived nodes must have a replayable transform in the CAS (ADR-004)
    if parents:
        t = m.get("transform", {}) if isinstance(m, dict) else {}
        tdigest = t.get("digest") if isinstance(t, dict) else None
        if isinstance(tdigest, str) and HEX64.match(tdigest):
            if not cas.object_path(tdigest).exists():
                errors.append(
                    f"derived node transform not in CAS: {tdigest} "
                    "(ingest with --transform-file)"
                )

    # 6) retraction status (ADR-013): a warning by default, an error under
    # --deny-retracted. Retraction is epistemic status, not deletion.
    if is_retracted(repo_root, node_id):
        try:
            reason = read_retraction(repo_root, node_id).get("reason", "unspecified")
        except Exception:
            reason = "unreadable retraction record"
        msg = f"retracted: {reason}"
        if deny_retracted:
            errors.append(msg)
        else:
            warnings.append(msg)

    # 7) optional derivation replay (stronger verification)
    if replay and len(errors) == 0:
        from ledger.replay import replay_node

        rr = replay_node(repo_root, node_id)
        if not rr.ok:
            errors.extend([f"replay: {e}" for e in rr.errors])

    return VerifyResult(ok=(len(errors) == 0), errors=errors, warnings=warnings)


def verify_reachable(
    repo_root: Path,
    root_id: str,
    replay: bool = False,
    deny_retracted: bool = False,
) -> VerifyResult:
    """DFS with memoization; validates all reachable nodes. Cycle-safe."""

    errors: List[str] = []
    warnings: List[str] = []
    seen: Set[str] = set()
    stack: List[str] = [root_id]

    while stack:
        nid = stack.pop()
        if nid in seen:
            continue
        seen.add(nid)

        r = verify_node(repo_root, nid, replay=replay, deny_retracted=deny_retracted)
        if not r.ok:
            errors.extend([f"{nid}: {e}" for e in r.errors])
        warnings.extend([f"{nid}: {w}" for w in r.warnings])

        try:
            m = read_node_manifest(repo_root, nid)
            parents = m.get("parents", [])
            if isinstance(parents, list):
                for p in parents:
                    if isinstance(p, str) and HEX64.match(p):
                        stack.append(p)
        except Exception as e:
            errors.append(f"{nid}: failed reading manifest: {e}")

    return VerifyResult(ok=(len(errors) == 0), errors=errors, warnings=warnings)


def fsck(repo_root: Path, replay: bool = False) -> VerifyResult:
    """Audit the whole store, including valid-but-unreachable nodes.

    Checks every manifest (name, schema, object, parents), every CAS blob
    (hashes to its own name; no stray files), and every ref (well-formed,
    manifest exists).
    """

    errors: List[str] = []

    # Manifests
    nodes_dir = repo_root / "ledger" / "nodes"
    if nodes_dir.is_dir():
        for mf in sorted(nodes_dir.iterdir()):
            if mf.name == ".keep":
                continue
            if not mf.name.endswith(".json") or not HEX64.match(mf.name[:-5]):
                errors.append(f"stray file in nodes/: {mf.name}")
                continue
            r = verify_node(repo_root, mf.name[:-5], replay=replay)
            if not r.ok:
                errors.extend([f"{mf.name[:-5]}: {e}" for e in r.errors])

    # Objects
    objects_dir = repo_root / "ledger" / "objects"
    if objects_dir.is_dir():
        for entry in sorted(objects_dir.rglob("*")):
            if not entry.is_file() or entry.name == ".keep":
                continue
            if not HEX64.match(entry.name):
                errors.append(f"stray file in objects/: {entry.relative_to(objects_dir)}")
                continue
            if entry.parent.name != entry.name[:2]:
                errors.append(f"mis-sharded object: {entry.relative_to(objects_dir)}")
            digest = sha256_file(entry)
            if digest != entry.name:
                errors.append(f"object corrupt: {entry.name} hashes to {digest}")

    # Refs
    refs_dir = repo_root / "ledger" / "refs"
    if refs_dir.is_dir():
        for rf in sorted(refs_dir.iterdir()):
            if rf.name == ".keep" or not rf.is_file():
                continue
            value = rf.read_text(encoding="utf-8").strip()
            if not HEX64.match(value):
                errors.append(f"ref {rf.name}: not a node id: {value!r}")
                continue
            if not node_manifest_path(repo_root, value).is_file():
                errors.append(f"ref {rf.name}: dangling (no manifest for {value})")

    # Retractions (ADR-013): structural audit; being retracted is not an error.
    retr_dir = repo_root / "ledger" / "retractions"
    if retr_dir.is_dir():
        import json as _json

        for rf in sorted(retr_dir.iterdir()):
            if rf.name == ".keep" or not rf.is_file():
                continue
            if not rf.name.endswith(".json") or not HEX64.match(rf.name[:-5]):
                errors.append(f"stray file in retractions/: {rf.name}")
                continue
            try:
                rec = _json.loads(rf.read_text(encoding="utf-8"))
            except Exception as e:
                errors.append(f"retraction {rf.name}: unreadable: {e}")
                continue
            errors.extend(
                f"retraction {rf.name}: {e}" for e in validate_retraction(repo_root, rec)
            )
            if isinstance(rec, dict):
                if rec.get("retracts") != rf.name[:-5]:
                    errors.append(
                        f"retraction {rf.name}: retracts field mismatch: "
                        f"{rec.get('retracts')!r}"
                    )
                target = rec.get("retracts")
                if isinstance(target, str) and HEX64.match(target):
                    if not node_manifest_path(repo_root, target).is_file():
                        errors.append(
                            f"retraction {rf.name}: no manifest for retracted node"
                        )
                succ = rec.get("superseded_by")
                if isinstance(succ, str) and HEX64.match(succ):
                    if not node_manifest_path(repo_root, succ).is_file():
                        errors.append(
                            f"retraction {rf.name}: dangling successor {succ}"
                        )

    return VerifyResult(ok=(len(errors) == 0), errors=errors)
