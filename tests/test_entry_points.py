from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _run(
    command: list[str], cwd: Path, python_path: str | None = None
) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    if python_path is not None:
        environment["PYTHONPATH"] = python_path
    return subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def test_direct_main_script_supports_help() -> None:
    package_directory = Path("src/omnireader").resolve()
    result = _run([sys.executable, "main.py", "--help"], package_directory)

    assert result.returncode == 0, result.stderr
    assert "Read documents aloud" in result.stdout


def test_module_entry_point_supports_help() -> None:
    repository = Path.cwd()
    result = _run(
        [sys.executable, "-m", "omnireader", "--help"],
        repository,
        str(repository / "src"),
    )

    assert result.returncode == 0, result.stderr
    assert "Read documents aloud" in result.stdout
