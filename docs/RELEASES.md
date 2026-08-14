# Release notes

## v0.1.0 — 2026-08-14

First tagged baseline of the reconstructed epistemic ledger: content-addressed
store, schema-gated node manifests, append-only governance (local pre-commit
hook + hosted gates), retraction as epistemic status (ADR-013), and
operator-only derivation replay (Regime B, ADR-002). The frozen Sprint-1
surface is byte-pinned via `fixtures/FROZEN_SHA256SUMS` (ADR-014); governing
decisions are ADR-001…ADR-019 in `docs/decisions.md`.

Verified at this tag: the full gate (87 tests, append-only check, 28 frozen
pins, `fsck`, Sprint-1 fencepost) green on hosted Python 3.11 and on a
clean-clone Python 3.14 environment with `pip check`; hosted negative-case
failures observed for protected modification, protected deletion, frozen
drift without a pin update, and CAS corruption; branch protection requires
all three gate jobs and prohibits force-pushes and deletion of `main`.

### Guarantee boundary

What this release guarantees — and what it does not:

- **Provenance integrity is guaranteed.** Recorded bytes, manifests, and
  parent links are tamper-evident: verification recomputes every hash, and
  the gates refuse history that modifies protected paths.
- **Root truth is not guaranteed.** A root node records that bytes were
  admitted, not that they are true, authentic, or well-sourced.
- **Transforms are not safe merely because they are recorded.** The CAS
  stores transform bytes; it does not vet them. Executing a transform is a
  trust decision the operator makes.
- **Replay is operator-only.** CI never executes transforms (Regime B).
  Replay runs only in an explicitly trusted environment (ADR-002).
- **This is not a secrets system.** Never ingest credentials or private
  material; retraction marks epistemic status, it does not erase bytes
  (`docs/RETRACTION.md` documents the break-glass ceremony).
- **Artifact identity does not distinguish alternate derivations producing
  identical bytes.** Each byte-identical artifact carries exactly one
  canonical provenance assertion (ADR-019).
