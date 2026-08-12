from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize("name", ["run.sh", "test.sh", "_activate_venv.sh"])
def test_shell_script_is_executable_and_valid(name: str) -> None:
    path = Path("scripts") / name

    assert os.access(path, os.X_OK)
    result = subprocess.run(
        ["bash", "-n", str(path)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_run_script_explains_missing_virtual_environment(tmp_path: Path) -> None:
    environment = {**os.environ, "OMNIREADER_VENV": str(tmp_path / "missing")}
    result = subprocess.run(
        ["bash", "scripts/run.sh", "--help"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "virtual environment not found" in result.stderr
    assert "python3 -m venv .venv" in result.stderr
