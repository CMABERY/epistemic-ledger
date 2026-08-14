# System intent (LAW)

**Prime objective**: maintain an append-only, content-addressed derivation
ledger whose meaning is mechanically unavoidable: schema-gated interpretation
plus deterministic verification from a single entrypoint.

## Non-negotiable invariants

- **Identity**: semantic identity is SHA-256 of bytes as defined by LAW —
  raw artifact bytes for node ids; `canon_json_bytes` for canonical JSON
  material. If the canonical-bytes function changes, every derived hash in the
  system becomes invalid at once. That is intentional.
- **Append-only**: `ledger/objects/`, `ledger/nodes/`, `ledger/deltas/`, and
  `ledger/retractions/` are add-only. Modification, rename, copy, or deletion
  under those prefixes is forbidden (enforced by CI and the pre-commit hook;
  the only exception path is `docs/RETRACTION.md`, Layer 3).
- **Interpretation is gated**: a manifest is not "a node" unless it validates
  against the pinned node schema (`ledger/schema/NODE_SCHEMA_SHA256`).
- **Verification is executable**: repo truth is what `ci/run_checks.sh`
  accepts; CI runs no other logic. Per LAW-0001, names and narratives are
  non-normative — tests and pinned bytes are normative.

## Law → Execution gradient (no upward dependencies)

```
LAW                     docs/, schemas/, ledger/schema/   (pinned meaning)
  ↓
DETERMINISTIC TRANSFORMS src/, transforms/                (pure code)
  ↓
EVIDENCE                fixtures/, ledger/                (frozen + accumulated bytes)
  ↓
EXECUTION               ci/, tools/                       (gates that check, never decide)
```

A lower layer may read upward definitions; nothing above depends on anything
below. Execution verifies; it never interprets.

## What this substrate guarantees — and what it does not

It guarantees **provenance integrity**: this artifact was derived from these
parents by this transform, verifiable by recomputation. It does not guarantee
truth of root inputs, safety of transforms, or secrecy of contents — see
`docs/NON_GOALS.md`. Trust originates at the roots and in transform semantics;
the DAG only transports it.
