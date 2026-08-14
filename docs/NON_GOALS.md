# Non-goals (LAW)

Recovered from the original design and reaffirmed. This substrate is **not
responsible for**:

- **Transform safety**: executing arbitrary transforms is not considered safe
  by default. Replay executes code (Regime B: CI never runs it; operators run
  it only in explicitly trusted environments).
- **Sandboxing**: no claim of secure sandboxing exists unless an
  `env_digest`-bound execution substrate is implemented and enforced. None is.
- **Bit-for-bit determinism across machines** without pinned inputs and an
  explicitly bound execution environment. The pinning ladder —
  `requirements.lock` → `--runner` → `--env-digest` → hermetic execution — is
  evidence, not enforcement; the last rung is aspirational.
- **Domain meaning**: the ledger kernel does not interpret business or domain
  semantics; it accounts for derivations.
- **Ref immutability**: refs are convenience pointers and may move.
  Immutability is provided only by content-addressed objects, nodes, and
  retraction records.
- **Secrecy/privacy**: **a Git repo is not a secrets system.** Never ingest
  credential material. When prevention fails, the only remedy is the
  break-glass ceremony in `docs/RETRACTION.md` — damage control, not privacy.
