from __future__ import annotations

import json
from typing import Any

from .db import Database

DEFAULTS: dict[str, Any] = {
    "tts.backend": "edge",
    "tts.voice.edge": "en-US-AriaNeural",
    "tts.voice.piper": "",
    "tts.rate": 1.0,
    "tts.pitch": 0.0,
    "tts.buffer_depth": 2,
    "tts.forced_alignment": False,
    "filters.skip_headers_footers": True,
    "filters.skip_hidden": True,
    "filters.skip_likely_hidden": False,
    "filters.skip_code": False,
    "filters.skip_captions": False,
    "reading.reopen_tabs": True,
    "reading.auto_scroll": True,
    "reading.font_family": "Sans Serif",
    "reading.font_size": 14,
    "reading.word_color": "#ffd54f",
    "reading.sentence_color": "#fff3bf",
    "storage.cache_max_mb": 512,
}


class SettingsRepository:
    def __init__(self, database: Database) -> None:
        self.db = database

    def get(self, key: str, default: Any = None) -> Any:
        row = (
            self.db.connection()
            .execute("SELECT value FROM settings WHERE key = ?", (key,))
            .fetchone()
        )
        if row is None:
            return DEFAULTS.get(key, default)
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return default

    def set(self, key: str, value: Any) -> None:
        encoded = json.dumps(value)
        with self.db.transaction() as connection:
            connection.execute(
                """INSERT INTO settings(key, value) VALUES (?, ?)
                   ON CONFLICT(key) DO UPDATE SET value=excluded.value""",
                (key, encoded),
            )

    def all(self) -> dict[str, Any]:
        values = dict(DEFAULTS)
        for row in self.db.connection().execute("SELECT key, value FROM settings"):
            try:
                values[row[0]] = json.loads(row[1])
            except json.JSONDecodeError:
                continue
        return values
