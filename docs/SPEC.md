# Kernel specification

The minimal accounting kernel (MAK): an append-only, content-addressed
derivation DAG embedded in the git worktree. See `docs/SYSTEM_INTENT.md` for
invariants, `docs/decisions.md` for why each choice was made.

## Node identity

`node_id = sha256(raw artifact bytes)`, bare lowercase hex (`^[a-f0-9]{64}$`).
No prefix, no domain separation.

## Store layout

| Path | Mutability | Contents |
|------|-----------|----------|
| `ledger/objects/<hex[:2]>/<digest>` | add-only | CAS blobs (artifacts, transforms, env descriptors) |
| `ledger/nodes/<id>.json` | add-only | node manifests |
| `ledger/retractions/<id>.json` | add-only | retraction records (ADR-013) |
| `ledger/deltas/` | add-only (reserved) | RCWP delta captures — tooling deferred (ADR-017) |
| `ledger/refs/<name>` | mutable | convenience pointers; standard verification root: `main` |
| `ledger/schema/` | versioned via pins | `node.schema.json` (pin `NODE_SCHEMA_SHA256`), `retraction.schema.json` |

## Node manifest

Validates against the pinned schema (`900af7e4…c266`, reused verbatim from the
original). Serialization is frozen: `json.dumps(payload, indent=2,
sort_keys=True) + "\n"`, created atomically with `open(mode="x")` (ADR-015).

- **Semantic fields**: `id`, `parents` (ordered), `transform.digest`,
  `transform.params`; `transform.runner` / `transform.env_digest` are semantic
  if present.
- **Non-semantic**: `transform.name` (display only), `meta` (notes,
  authorship, hints — never relied upon).

## Derivation contract

`(parents, transform, params) -> child`, deterministic.

- **Derived nodes** (`parents != []`) require the transform bytes in the CAS
  (`--transform-file`), enforced at ingest and verify (ADR-004).
- **Root/admission nodes** (`parents == []`) carry the sentinel
  `transform.digest = sha256(b"") = e3b0c442…` (ADR-005) and pass replay
  trivially.

### Replay (operator-only; Regime B, ADR-002)

```
<runner...> <transform_script> \
  --parents-manifest <wd>/parents.json \
  --parents-dir <wd>/parents \
  --params-path <wd>/params.json \
  --out <wd>/out.bin
```

Success iff `sha256(out.bin) == node_id`. Default runner `["python3"]`.
CI never executes transforms; it verifies structure only.

## Verification layers

1. `ledger verify <id|ref>` — manifest exists, schema-valid, object hash
   matches id, parent manifests exist, derived transform in CAS; retracted
   nodes warn (fail with `--deny-retracted`); `--replay` recomputes.
2. `ledger verify-reachable [id|ref]` — the above over the transitive parent
   closure (default root: ref `main`); cycle-safe.
3. `ledger fsck` — whole-store audit including valid-but-unreachable nodes:
   every manifest, every blob (hashes to its own name, correctly sharded),
   every ref (well-formed, non-dangling), every retraction record.

## CLI surface

`ledger hash | ingest | verify | verify-reachable | replay | fsck | retract |
refs set|get` — see `--help` per subcommand. Recovered contract: hash, ingest,
verify, verify-reachable, replay, refs. **Additive** (not recovered behavior):
`fsck`, `retract`, `--deny-retracted`, ref-name resolution in id positions,
refs refusing dangling targets, ingest refusing schema-invalid manifests.

## NRE Sprint-1 fencepost (frozen)

`nre-verify-fixtures --all` must exit 0: canon vectors
(`fixtures/vectors/`) plus five fixture cases (`fixtures/cases/`) compared by
whole-envelope equality against frozen `expected.json` bytes. Envelope exit
codes `{0, 10, 11, 12}` are frozen by those bytes; process codes are
`0 / 2 usage / 20 mismatch / 40 internal` (ADR-006). The entire frozen
surface is byte-pinned in `fixtures/FROZEN_SHA256SUMS` (ADR-014).

## Governance enforcement

- Pre-commit hook (`tools/install_hooks.py`): append-only check on staged
  changes always; frozen pins + full fencepost gate when fencepost paths are
  staged.
- CI (`.github/workflows/ci.yml` → `ci/*.sh`): tests, append-only vs merge
  base (loud failure when no merge base exists, ADR-016), frozen pins, fsck,
  fencepost gate. No replay in CI (Regime B).
- Recommended branch protection when pushed to a remote: disable force-push,
  require the three gate jobs.
