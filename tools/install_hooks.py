"""Install the repository pre-commit hook into .git/hooks.

Idempotent: re-running over an identical hook is a no-op. Refuses to
overwrite a foreign (different-content) hook unless --force is given.
"""

from __future__ import annotations

import argparse
import stat
import subprocess
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Install repo git hooks")
    ap.add_argument(
        "--force", action="store_true", help="Overwrite a foreign existing hook."
    )
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    src = repo_root / "tools" / "hooks" / "pre-commit"

    try:
        git_dir = Path(
            subprocess.check_output(
                ["git", "rev-parse", "--git-dir"], text=True, cwd=repo_root
            ).strip()
        )
    except subprocess.CalledProcessError as e:
        print(f"not a git repository? {e}", file=sys.stderr)
        return 3
    if not git_dir.is_absolute():
        git_dir = repo_root / git_dir

    dst = git_dir / "hooks" / "pre-commit"
    dst.parent.mkdir(parents=True, exist_ok=True)

    content = src.read_bytes()
    if dst.exists():
        if dst.read_bytes() == content:
            print(f"pre-commit hook already installed: {dst}")
            return 0
        if not args.force:
            print(
                f"refusing to overwrite existing (different) hook: {dst}\n"
                "  re-run with --force to replace it",
                file=sys.stderr,
            )
            return 2

    dst.write_bytes(content)
    dst.chmod(dst.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"installed pre-commit hook: {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
