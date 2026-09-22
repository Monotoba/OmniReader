import subprocess
import sys
from importlib.metadata import version

import pytest


def test_release_tag_accepts_matching_version() -> None:
    package_version = version("omnireader")
    result = subprocess.run(
        [sys.executable, "scripts/check_release_tag.py", f"v{package_version}"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert f"matches package version {package_version}" in result.stdout


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
