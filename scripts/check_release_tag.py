#!/usr/bin/env python3
"""Fail when a release tag does not match the project version."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def project_version(pyproject: Path) -> str:
    content = pyproject.read_text(encoding="utf-8")
    project = re.search(r"(?ms)^\[project\]\s*(.*?)(?=^\[|\Z)", content)
    if project is None:
        raise ValueError("pyproject.toml has no [project] table")
    version = re.search(
        r'^version\s*=\s*["\']([^"\']+)["\']\s*$', project.group(1), re.M
    )
    if version is None:
        raise ValueError("[project] has no static version")
    return version.group(1)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"Usage: {argv[0]} v<VERSION>", file=sys.stderr)
        return 2
    version = project_version(Path(__file__).resolve().parents[1] / "pyproject.toml")
    expected = f"v{version}"
    if argv[1] != expected:
        print(
            f"Release tag {argv[1]!r} does not match package version {expected!r}",
            file=sys.stderr,
        )
        return 1
    print(f"Release tag {argv[1]} matches package version {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
