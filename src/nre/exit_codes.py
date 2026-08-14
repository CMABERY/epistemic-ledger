"""NRE exit codes (ADR-006).

Two disjoint layers; envelope codes are never surfaced as process codes.

Envelope codes are FROZEN by fixture bytes (`expected.json` pins them;
LAW-0001: tests are normative). Process codes govern the CLI itself.
"""

from __future__ import annotations

# ---- Envelope codes (frozen by fixture bytes) ----
EXIT_OK = 0
EXIT_WSS_HASH_INTEGRITY_FAILED = 10
EXIT_DSS_REQUIRES_NON_NULL_HASH = 11
EXIT_SCHEMA_VALIDATION_FAILED = 12

# ---- Process-level codes (this CLI; not envelope material) ----
PROC_OK = 0
PROC_USAGE = 2
PROC_FIXTURE_MISMATCH = 20
PROC_INTERNAL_ERROR = 40
