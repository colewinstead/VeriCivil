"""Identify documentation-only changes without skipping the required CI job."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import PurePosixPath


def requires_release(paths: list[str]) -> bool:
    """Unknown files require a release; only source documentation is exempt."""
    return any(
        PurePosixPath(path).suffix.lower() not in {".md", ".rst"}
        and path not in {"LICENSE", "LICENSE.txt", "LICENSE.md"}
        for path in paths
    )


def changed_paths(base: str, head: str, *, merge_base: bool = False, cwd: str | None = None) -> list[str]:
    # Initial branch pushes have no parent to compare, so classify all files.
    if not base or set(base) == {"0"}:
        command = ["git", "ls-tree", "-r", "--name-only", "-z", head]
    else:
        command = ["git", "diff", "--name-only", "--no-renames", "-z"]
        if merge_base:
            command.append("--merge-base")
        command.extend([base, head, "--"])
    output = subprocess.check_output(command, cwd=cwd)
    return [path.decode("utf-8", errors="surrogateescape") for path in output.split(b"\0") if path]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--merge-base", action="store_true")
    args = parser.parse_args()
    paths = changed_paths(args.base, args.head, merge_base=args.merge_base)
    print("true" if requires_release(paths) else "false")


if __name__ == "__main__":
    main()
