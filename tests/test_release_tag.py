import subprocess
import sys

import pytest


def test_release_tag_accepts_matching_version() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_release_tag.py", "v0.1.0"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "matches package version 0.1.0" in result.stdout


@pytest.mark.parametrize("tag", ["0.1.0", "v9.9.9", "latest"])
def test_release_tag_rejects_mismatches(tag: str) -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_release_tag.py", tag],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "does not match package version" in result.stderr
