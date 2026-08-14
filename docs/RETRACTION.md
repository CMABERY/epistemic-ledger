# Retraction, supersession, and the break-glass ceremony

The ledger is append-only. Mistakes are inevitable. This document defines the
governed exception paths **before** they are needed (ADR-013), so the invariant
never gets broken ad hoc under pressure.

## Layer 1 — Supersession (routine)

A wrong-but-harmless node needs no ceremony. Ingest the corrected node and
move refs:

```bash
ledger ingest corrected.bin --parent <...> --transform-file <...>
ledger refs set main <new_id>
```

The wrong node remains in the DAG as history. Content addressing already
guarantees nobody can mistake it for the successor.

## Layer 2 — Retraction (epistemic status, append-only)

When a node must be *marked* as not endorsed — wrong result, bad input,
misleading artifact — append a retraction record:

```bash
ledger retract <id-or-ref> --reason "why" [--superseded-by <id-or-ref>]
```

This creates immutable `ledger/retractions/<node_id>.json` (a protected
add-only path). Effects:

- `ledger verify` / `verify-reachable` emit a **warning** for retracted nodes;
  with `--deny-retracted` they **fail**.
- `ledger fsck` audits every retraction record structurally.
- Nothing is deleted. A retraction cannot be undone (append a successor node
  and point refs at it instead).

## Layer 3 — Break-glass history rewrite (BREAK-GLASS-HISTORY-REWRITE)

The only true deletion. Justified **only** by:

- credential/secret material ingested into `ledger/objects/`,
- legally non-retainable content,
- confirmed poisoned artifacts whose continued presence is itself a hazard.

"Embarrassing" or "wrong" never qualifies — that is Layer 2.

**Kill switch / authorization**: requires an explicit, recorded user decision
naming the exact digests to remove. No agent may initiate or perform this
unilaterally.

Procedure:

1. **Freeze**: stop all ingest; note current HEAD sha in the decision record.
2. **Enumerate**: list affected object digests, node manifests, retraction
   records, and every ref or child manifest referencing them.
3. **Retract first**: append retraction records for affected nodes while
   history still exists (Layer 2), so the epistemic record survives the
   rewrite.
4. **Rewrite**: remove the offending blobs from history with `git filter-repo`
   on a fresh clone; force-push with `--force-with-lease` only, to branches
   the owner controls.
5. **Re-pin**: if any frozen file was touched, regenerate
   `fixtures/FROZEN_SHA256SUMS` and record why.
6. **Ratify**: append a decision-log entry (what, why, old HEAD, new HEAD,
   date, who authorized) — the rewrite itself must be provenanced.
7. **Verify**: run the full gate (`ci/run_checks.sh`); confirm every replica
   and clone is re-synced or destroyed; rotate any exposed credentials.

Post-condition: the ledger is again append-only from the new HEAD, and the
decision log explains the discontinuity. A rewrite without steps 3, 6, and 7
is a governance failure, not a shortcut.

## Non-goals

Secrecy is out of scope by design: **a Git repo is not a secrets system**
(see `docs/NON_GOALS.md`). Layer 3 exists precisely because prevention will
eventually fail; it is damage control, not a privacy mechanism.
