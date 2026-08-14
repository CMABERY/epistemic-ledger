# Epistemic Ledger

An append-only, content-addressed derivation ledger embedded in Git, plus a
frozen executable verifier gate. Deliberate reconstruction of the 4GARTHA
minimal accounting kernel.

**Provenance**: frozen contracts (schemas, fixture vectors, verifier
semantics) mined verbatim from `github.com/CMABERY/4GARTHA` @ `2ab510f` and
byte-pinned in `fixtures/FROZEN_SHA256SUMS`; everything else redesigned from
scratch with every decision recorded in `docs/decisions.md`.

## What it is

- **Kernel** (`src/ledger/`): CAS + immutable node manifests + refs.
  `node_id = sha256(artifact bytes)`. Derivations are replayable:
  `(parents, transform, params) -> child`, verified by recomputation.
- **Governance** (`tools/`, `ci/`): `ledger/objects|nodes|deltas|retractions`
  are add-only, enforced by CI and a pre-commit hook (rename-defeat blocked).
  Retraction is an append, never a deletion (`docs/RETRACTION.md`).
- **Sprint-1 fencepost** (`src/nre/`, `fixtures/`, `schemas/`): the frozen
  `nre-verify-fixtures --all` acceptance gate — canon vectors + five fixture
  cases compared by whole-envelope byte equality.

What it guarantees is **provenance integrity**, not truth: garbage roots
yield immutably-provenanced garbage. See `docs/SYSTEM_INTENT.md` and
`docs/NON_GOALS.md`.

## Quickstart

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.lock
pip install -e . --no-deps
python tools/install_hooks.py
```

Acceptance gates (what CI runs):

```bash
bash ci/run_checks.sh        # tests + ledger gate + fencepost
nre-verify-fixtures --all    # Sprint-1 gate alone
```

Ledger usage:

```bash
ledger ingest artifact.bin --note "root evidence"          # root node
ledger ingest out.bin --parent <id> --parent <id> \
       --transform-file transforms/concat_parents.py \
       --params-json '{"suffix": "!"}'                     # derived node
ledger refs set main <id>
ledger verify-reachable                # structure (default root: main)
ledger verify-reachable --replay       # + recompute derivations (operator-only)
ledger fsck                            # whole-store audit
ledger retract <id> --reason "bad input" --superseded-by <id>
```

## Layout

```
docs/         LAW: intent, non-goals, spec, retraction ceremony, decision log
schemas/      NRE artifact schema (frozen, pinned)
ledger/       the store: objects/ nodes/ refs/ retractions/ deltas/ schema/
src/ledger/   kernel        src/nre/   fencepost verifier
fixtures/     frozen vectors + cases + FROZEN_SHA256SUMS
transforms/   example replayable transform (mutable; manifests pin digests)
tools/        append-only gate, frozen pins, hooks
ci/           gate scripts (CI runs exactly these)
```

## Deferred (ADR-017)

TPM root-entropy fixtures, RCWP delta-capture tooling (path reserved at
`ledger/deltas/`), and the P1x/P2x/P3x canon extensions.
