from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    override = os.getenv("OMNIREADER_DATA_DIR")
    base = (
        Path(override) if override else Path.home() / ".local" / "share" / "omnireader"
    )
    base.mkdir(parents=True, exist_ok=True)
    return base


def cache_dir() -> Path:
    override = os.getenv("OMNIREADER_CACHE_DIR")
    base = Path(override) if override else Path.home() / ".cache" / "omnireader"
    base.mkdir(parents=True, exist_ok=True)
    return base


def database_path() -> Path:
    return data_dir() / "library.db"


def piper_voices_dir() -> Path:
    return data_dir() / "piper-voices"
