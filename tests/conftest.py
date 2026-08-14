from __future__ import annotations

import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def ledger_repo(tmp_path: Path) -> Path:
    """A scratch ledger repo with the pinned node schema installed."""

    for d in ("objects", "nodes", "refs", "retractions"):
        (tmp_path / "ledger" / d).mkdir(parents=True)
    schema_dir = tmp_path / "ledger" / "schema"
    schema_dir.mkdir()
    for f in ("node.schema.json", "NODE_SCHEMA_SHA256", "retraction.schema.json"):
        shutil.copy(REPO_ROOT / "ledger" / "schema" / f, schema_dir / f)
    return tmp_path
