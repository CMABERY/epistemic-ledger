"""Scratch-git-repo matrix for tools/check_append_only.py.

Runs the real script via subprocess against throwaway repos, covering the
proven decision rules (incl. the rename-out defeat) and the ADR-016
merge-base/root-commit hardening.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools" / "check_append_only.py"

# Scratch repos must see stock git behavior, not the developer's global or
# system config: commit signing would drag in an external agent (flaky and
# signs throwaway commits with a real key), and diff/rename settings could
# change the very `--name-status` output the script under test parses.
GIT_ENV = {
    **os.environ,
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
}


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args],
        text=True,
        stderr=subprocess.STDOUT,
        env=GIT_ENV,
    )


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "scratch"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.invalid")
    (repo / "ledger" / "nodes").mkdir(parents=True)
    (repo / "ledger" / "objects" / "aa").mkdir(parents=True)
    (repo / "other").mkdir()
    (repo / "ledger" / "nodes" / ("a" * 64 + ".json")).write_text("{}\n")
    (repo / "ledger" / "objects" / "aa" / ("a" * 64)).write_text("blob\n")
    (repo / "other" / "file.txt").write_text("hello\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "seed")
    return repo


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=repo,
        text=True,
        capture_output=True,
        env=GIT_ENV,
    )


def _commit_all(repo: Path, msg: str) -> None:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)


def test_addition_ok(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "ledger" / "nodes" / ("b" * 64 + ".json")).write_text("{}\n")
    _commit_all(repo, "add node")
    r = _run(repo)
    assert r.returncode == 0, r.stderr
    assert "OK" in r.stdout


def test_modification_rejected(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "ledger" / "nodes" / ("a" * 64 + ".json")).write_text('{"tampered": 1}\n')
    _commit_all(repo, "tamper")
    r = _run(repo)
    assert r.returncode == 2
    assert "append-only invariant violated" in r.stderr


def test_deletion_rejected(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "ledger" / "objects" / "aa" / ("a" * 64)).unlink()
    _commit_all(repo, "delete blob")
    r = _run(repo)
    assert r.returncode == 2


def test_rename_out_rejected(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _git(repo, "mv", "ledger/nodes/" + "a" * 64 + ".json", "other/escaped.json")
    _git(repo, "commit", "-q", "-m", "rename out")
    r = _run(repo)
    assert r.returncode == 2, "rename-out must be a violation (old path protected)"


def test_rename_in_rejected(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _git(repo, "mv", "other/file.txt", "ledger/nodes/smuggled.json")
    _git(repo, "commit", "-q", "-m", "rename in")
    r = _run(repo)
    assert r.returncode == 2, "rename-in must be a violation (R status, not A)"


def test_unprotected_changes_ok(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "other" / "file.txt").write_text("changed\n")
    (repo / "other" / "new.txt").write_text("new\n")
    _commit_all(repo, "normal work")
    r = _run(repo)
    assert r.returncode == 0


def test_cached_mode(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    (repo / "ledger" / "nodes" / ("c" * 64 + ".json")).write_text("{}\n")
    _git(repo, "add", "-A")
    r = _run(repo, "--cached")
    assert r.returncode == 0, r.stderr

    (repo / "ledger" / "nodes" / ("a" * 64 + ".json")).write_text("tampered\n")
    _git(repo, "add", "-A")
    r2 = _run(repo, "--cached")
    assert r2.returncode == 2


def test_base_ref_mode(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    _git(repo, "branch", "base")
    (repo / "ledger" / "nodes" / ("d" * 64 + ".json")).write_text("{}\n")
    _commit_all(repo, "add on top")
    assert _run(repo, "base").returncode == 0

    (repo / "ledger" / "nodes" / ("a" * 64 + ".json")).write_text("tampered\n")
    _commit_all(repo, "tamper on top")
    assert _run(repo, "base").returncode == 2


def test_multi_commit_range_needs_explicit_base(tmp_path: Path) -> None:
    """A violation buried below the tip commit is invisible to the bare
    HEAD~1...HEAD fallback and caught only via an explicit base — the reason
    CI must always pass one (push: previous tip; PR: origin/<base>)."""
    repo = _init_repo(tmp_path)
    _git(repo, "branch", "base")
    (repo / "ledger" / "nodes" / ("a" * 64 + ".json")).write_text("tampered\n")
    _commit_all(repo, "tamper mid-push")
    (repo / "other" / "innocent.txt").write_text("later\n")
    _commit_all(repo, "innocent tip")
    assert _run(repo).returncode == 0, "fallback range is blind below the tip"
    assert _run(repo, "base").returncode == 2, "explicit base must catch it"


def test_cached_and_base_ref_conflict(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    r = _run(repo, "main", "--cached")
    assert r.returncode == 3


def test_missing_merge_base_loud(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    r = _run(repo, "no-such-ref")
    assert r.returncode == 3
    assert "no merge base" in r.stderr
    assert "fetch-depth" in r.stderr


def test_root_commit_handled(tmp_path: Path) -> None:
    repo = tmp_path / "rootonly"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.invalid")
    (repo / "ledger" / "nodes").mkdir(parents=True)
    (repo / "ledger" / "nodes" / ("a" * 64 + ".json")).write_text("{}\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "root")
    r = _run(repo)
    assert r.returncode == 0, r.stderr
