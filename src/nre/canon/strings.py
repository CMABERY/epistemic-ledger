"""P1 — Canonical string handling (frozen semantics).

Ported from 4GARTHA `canon/strings.py` (2ab510f). Deliberately narrow:
deterministic normalization primitives without policy.

ADR-008: NFC-only. The design-note trim/collapse/newline rules never shipped
and are NOT merged into this frozen primitive.
"""

from __future__ import annotations

import unicodedata


def normalize_string(s: str) -> str:
    """Return a canonicalized string.

    Rules (Sprint-1, frozen):
      - input must be `str`
      - Unicode normalization: NFC

    No trimming, case folding, or locale behavior is introduced at this layer.
    """

    if not isinstance(s, str):
        raise TypeError(f"expected str, got {type(s).__name__}")
    return unicodedata.normalize("NFC", s)
