"""tools/check_frozen.py: pinned frozen surface verification (ADR-014)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools" / "check_frozen.py"


def test_pristine_tree_passes() -> None:
    r = subprocess.run(
        [sys.executable, str(SCRIPT)], text=True, capture_output=True
    )
    assert r.returncode == 0, r.stderr
    assert "OK (28 files)" in r.stdout
