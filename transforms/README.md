# Transforms

Transforms are domain logic. The ledger only cares about one thing:

> given ordered parents and semantic params, the transform deterministically
> produces the child bytes.

This directory is freely mutable: code evolves; **manifests pin digests**.
A node's identity binds to the transform *bytes* stored in the CAS at ingest
time, never to a file here.

## Replay contract (v0)

Derived nodes must be ingested with `--transform-file path/to/transform.py`
(ADR-004) so the transform bytes live in the CAS. Replay (`ledger replay`)
executes the CAS copy by digest with the CLI contract:

```
<runner...> <transform_script> \
  --parents-manifest <workdir>/parents.json \
  --parents-dir <workdir>/parents \
  --params-path <workdir>/params.json \
  --out <workdir>/out.bin
```

Replay succeeds iff `sha256(out.bin)` equals the node id. Root nodes
(`parents: []`) pass trivially.

Replay executes code (Regime B, ADR-002): CI never runs it; operators run it
only in a trusted environment. Pin `--runner` (e.g. `--runner python3
--runner -I`) and `--env-digest` for stronger environment evidence.

See `concat_parents.py` for an example.
