"""ledger — minimal accounting kernel CLI.

Rewritten from 4GARTHA ``src/ledger/cli.py`` (2ab510f; the original file was
corrupted by a half-applied patch). Deliberate changes:
  - ADR-004: derived nodes require ``--transform-file`` (weak name-hash
    fallback removed),
  - ADR-005: root nodes get the sentinel transform digest sha256(b""),
  - ADR-015: no session lock; manifest creation is atomic,
  - new subcommand ``fsck``; ``verify-reachable`` accepts a ref name or id
    (default ref: ``main``); ``refs set`` refuses dangling targets.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from ledger.cas import CasPaths, sha256_file, store_blob
from ledger.manifest import Node, Transform, write_node_manifest
from ledger.refs import get_ref, resolve, set_ref
from ledger.schema import ROOT_TRANSFORM_DIGEST, validate_manifest
from ledger.verify import fsck, verify_node, verify_reachable


def repo_root_from_cwd() -> Path:
    # Walk up until we find a 'ledger/' directory.
    p = Path.cwd().resolve()
    for candidate in (p, *p.parents):
        if (candidate / "ledger").is_dir():
            return candidate
    raise SystemExit(
        "Could not find repo root (missing ./ledger directory). Run inside the repo."
    )


def _print_errors(errors: list[str]) -> None:
    for e in errors:
        print(e)


def cmd_hash(args: argparse.Namespace) -> int:
    p = Path(args.path)
    if not p.exists():
        raise SystemExit(f"no such file: {p}")
    print(sha256_file(p))
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    repo_root = repo_root_from_cwd()
    src = Path(args.path)
    if not src.exists():
        raise SystemExit(f"no such file: {src}")

    parents = args.parent or []
    if parents and not args.transform_file:
        raise SystemExit(
            "derived nodes (with --parent) require --transform-file (ADR-004): "
            "the transform bytes must live in the CAS for replay"
        )

    artifact_id = sha256_file(src)
    cas = CasPaths.from_repo_root(repo_root)
    store_blob(src, cas, artifact_id)

    if args.transform_file:
        tf = Path(args.transform_file)
        if not tf.exists():
            raise SystemExit(f"no such transform file: {tf}")
        transform_digest = sha256_file(tf)
        # Store transform definition in the CAS so it can be replayed by digest.
        store_blob(tf, cas, transform_digest)
        transform_name = args.transform or tf.name
    else:
        # Root/admission node (ADR-005).
        transform_digest = ROOT_TRANSFORM_DIGEST
        transform_name = args.transform or "admission"

    params: Dict[str, Any] = {}
    if args.params_json:
        params = json.loads(args.params_json)
        if not isinstance(params, dict):
            raise SystemExit("--params-json must decode to a JSON object")

    node = Node(
        id=artifact_id,
        parents=list(parents),
        transform=Transform(
            name=transform_name,
            digest=transform_digest,
            params=params,
            runner=args.runner,
            env_digest=args.env_digest,
        ),
        meta={"note": args.note} if args.note else None,
    )

    # Interpretation is gated: refuse to write a manifest that would not
    # validate against the pinned schema.
    payload = node.to_dict()
    schema_errors = validate_manifest(repo_root, payload)
    if schema_errors:
        _print_errors(schema_errors)
        raise SystemExit("refusing to write schema-invalid manifest")

    write_node_manifest(repo_root, node)

    print(artifact_id)
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    repo_root = repo_root_from_cwd()
    node_id = resolve(repo_root, args.id)
    r = verify_node(repo_root, node_id, replay=args.replay)
    if r.ok:
        print("OK")
        return 0
    _print_errors(r.errors)
    return 2


def cmd_verify_reachable(args: argparse.Namespace) -> int:
    repo_root = repo_root_from_cwd()
    node_id = resolve(repo_root, args.id)
    r = verify_reachable(repo_root, node_id, replay=args.replay)
    if r.ok:
        print("OK")
        return 0
    _print_errors(r.errors)
    return 2


def cmd_replay(args: argparse.Namespace) -> int:
    repo_root = repo_root_from_cwd()
    from ledger.replay import replay_node

    wd = Path(args.workdir).resolve() if args.workdir else None
    r = replay_node(repo_root, resolve(repo_root, args.id), workdir=wd, keep=args.keep)
    if r.ok:
        print("OK")
        return 0
    _print_errors(r.errors)
    return 2


def cmd_fsck(args: argparse.Namespace) -> int:
    repo_root = repo_root_from_cwd()
    r = fsck(repo_root, replay=args.replay)
    if r.ok:
        print("OK")
        return 0
    _print_errors(r.errors)
    return 2


def cmd_refs_set(args: argparse.Namespace) -> int:
    repo_root = repo_root_from_cwd()
    try:
        set_ref(repo_root, args.name, args.id.strip())
    except (ValueError, FileNotFoundError) as e:
        raise SystemExit(str(e))
    return 0


def cmd_refs_get(args: argparse.Namespace) -> int:
    repo_root = repo_root_from_cwd()
    try:
        print(get_ref(repo_root, args.name))
    except (ValueError, FileNotFoundError) as e:
        raise SystemExit(str(e))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ledger", description="Epistemic Ledger CLI (minimal accounting kernel)."
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    p_hash = sub.add_parser("hash", help="Compute sha256 of a file.")
    p_hash.add_argument("path")
    p_hash.set_defaults(fn=cmd_hash)

    p_ing = sub.add_parser(
        "ingest",
        help="Store artifact + write immutable node manifest (append-only).",
    )
    p_ing.add_argument("path")
    p_ing.add_argument(
        "--parent",
        action="append",
        help="Parent node id (sha256). May be repeated.",
    )
    p_ing.add_argument(
        "--transform",
        help="Transform display name (non-semantic; digest is the identity).",
    )
    p_ing.add_argument(
        "--transform-file",
        help="Path to transform definition file; digest = sha256(file). "
        "Required when any --parent is given (ADR-004).",
    )
    p_ing.add_argument(
        "--runner",
        action="append",
        help="Replay runner command prefix (repeatable), e.g. --runner python3 --runner -I.",
    )
    p_ing.add_argument(
        "--env-digest",
        help="sha256 of the execution environment description "
        "(lockfile/nix flake/container recipe), stored in CAS.",
    )
    p_ing.add_argument("--params-json", help="JSON object of semantic params (canonical).")
    p_ing.add_argument("--note", help="Non-semantic note.")
    p_ing.set_defaults(fn=cmd_ingest)

    p_ver = sub.add_parser(
        "verify",
        help="Verify node (schema + object hash + parents; optional replay).",
    )
    p_ver.add_argument("id", help="Node id or ref name.")
    p_ver.add_argument(
        "--replay",
        action="store_true",
        help="Also replay derivation (requires transform in CAS).",
    )
    p_ver.set_defaults(fn=cmd_verify)

    p_vr = sub.add_parser(
        "verify-reachable",
        help="Verify a node and all reachable ancestors (optional replay).",
    )
    p_vr.add_argument(
        "id",
        nargs="?",
        default="main",
        help="Node id or ref name (default: ref 'main').",
    )
    p_vr.add_argument(
        "--replay",
        action="store_true",
        help="Also replay derivations for reachable nodes.",
    )
    p_vr.set_defaults(fn=cmd_verify_reachable)

    p_rep = sub.add_parser("replay", help="Replay a node derivation and verify output hash.")
    p_rep.add_argument("id", help="Node id or ref name.")
    p_rep.add_argument(
        "--workdir",
        help="Optional directory to materialize inputs/output (useful for debugging).",
    )
    p_rep.add_argument(
        "--keep",
        action="store_true",
        help="Keep the workdir (when using an auto-temp dir) after replay.",
    )
    p_rep.set_defaults(fn=cmd_replay)

    p_fsck = sub.add_parser(
        "fsck",
        help="Audit the whole store: every manifest, blob, and ref (incl. unreachable).",
    )
    p_fsck.add_argument(
        "--replay",
        action="store_true",
        help="Also replay every derived node (operator-only; slow).",
    )
    p_fsck.set_defaults(fn=cmd_fsck)

    p_rs = sub.add_parser("refs", help="Manage mutable convenience refs.")
    rs = p_rs.add_subparsers(dest="refs_cmd", required=True)

    rs_set = rs.add_parser("set", help="Set ref to a node id (manifest must exist).")
    rs_set.add_argument("name")
    rs_set.add_argument("id")
    rs_set.set_defaults(fn=cmd_refs_set)

    rs_get = rs.add_parser("get", help="Get node id from ref.")
    rs_get.add_argument("name")
    rs_get.set_defaults(fn=cmd_refs_get)

    return p


def main(argv: list[str] | None = None) -> int:
    p = build_parser()
    args = p.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main())
