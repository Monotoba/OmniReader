from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from ..document.filters import FilterSettings
from ..document.model import NormalizedDocument, TextPosition
from .db import Database


@dataclass(frozen=True, slots=True)
class VoicePreferences:
    backend_name: str | None = None
    voice_id: str | None = None
    rate: float | None = None
    pitch: float | None = None


@dataclass(frozen=True, slots=True)
class ReadingState:
    block_id: str
    sentence_index: int = 0
    word_index: int = 0
    scroll_offset: int = 0

    @property
    def position(self) -> TextPosition:
        return TextPosition(self.block_id, self.sentence_index, self.word_index)


class DocumentsRepository:
    def __init__(self, database: Database) -> None:
        self.db = database

    def remember(self, document: NormalizedDocument, path: Path) -> None:
        with self.db.transaction() as connection:
            connection.execute(
                """INSERT INTO documents(doc_id, path, title, format)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(doc_id) DO UPDATE SET path=excluded.path,
                     title=excluded.title, format=excluded.format,
                     last_opened_at=CURRENT_TIMESTAMP""",
                (document.doc_id, str(path), document.title, path.suffix.casefold()),
            )

    def path_for(self, doc_id: str) -> Path | None:
        row = (
            self.db.connection()
            .execute("SELECT path FROM documents WHERE doc_id = ?", (doc_id,))
            .fetchone()
        )
        return Path(row[0]) if row else None

    def save_position(self, doc_id: str, state: ReadingState) -> None:
        with self.db.transaction() as connection:
            connection.execute(
                """INSERT INTO reading_state
                   (doc_id, block_id, sentence_index, word_index, scroll_offset)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(doc_id) DO UPDATE SET block_id=excluded.block_id,
                     sentence_index=excluded.sentence_index, word_index=excluded.word_index,
                     scroll_offset=excluded.scroll_offset, updated_at=CURRENT_TIMESTAMP""",
                (
                    doc_id,
                    state.block_id,
                    state.sentence_index,
                    state.word_index,
                    state.scroll_offset,
                ),
            )

    def position(self, doc_id: str) -> ReadingState | None:
        row = (
            self.db.connection()
            .execute(
                """SELECT block_id, sentence_index, word_index, scroll_offset
               FROM reading_state WHERE doc_id = ?""",
                (doc_id,),
            )
            .fetchone()
        )
        return ReadingState(*row) if row and row[0] else None

    def save_voice_preferences(
        self, doc_id: str, preferences: VoicePreferences
    ) -> None:
        with self.db.transaction() as connection:
            connection.execute(
                """INSERT INTO document_voice_prefs
                   (doc_id, backend_name, voice_id, rate, pitch)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(doc_id) DO UPDATE SET backend_name=excluded.backend_name,
                     voice_id=excluded.voice_id, rate=excluded.rate, pitch=excluded.pitch,
                     updated_at=CURRENT_TIMESTAMP""",
                (
                    doc_id,
                    preferences.backend_name,
                    preferences.voice_id,
                    preferences.rate,
                    preferences.pitch,
                ),
            )

    def voice_preferences(self, doc_id: str) -> VoicePreferences | None:
        row = (
            self.db.connection()
            .execute(
                """SELECT backend_name, voice_id, rate, pitch
               FROM document_voice_prefs WHERE doc_id = ?""",
                (doc_id,),
            )
            .fetchone()
        )
        return VoicePreferences(*row) if row else None

    def save_filters(self, doc_id: str, filters: FilterSettings) -> None:
        with self.db.transaction() as connection:
            connection.execute(
                """INSERT INTO document_filter_prefs(doc_id, value) VALUES (?, ?)
                   ON CONFLICT(doc_id) DO UPDATE SET value=excluded.value,
                     updated_at=CURRENT_TIMESTAMP""",
                (doc_id, json.dumps(asdict(filters))),
            )

    def filters(self, doc_id: str) -> FilterSettings | None:
        row = (
            self.db.connection()
            .execute(
                "SELECT value FROM document_filter_prefs WHERE doc_id = ?", (doc_id,)
            )
            .fetchone()
        )
        return FilterSettings(**json.loads(row[0])) if row else None

    def save_tabs(self, tabs: list[tuple[str, bool]]) -> None:
        with self.db.transaction() as connection:
            connection.execute("DELETE FROM open_tabs")
            connection.executemany(
                "INSERT INTO open_tabs(tab_order, doc_id, is_active) VALUES (?, ?, ?)",
                [
                    (order, doc_id, int(active))
                    for order, (doc_id, active) in enumerate(tabs)
                ],
            )

    def open_tabs(self) -> list[tuple[str, bool]]:
        rows = (
            self.db.connection()
            .execute("SELECT doc_id, is_active FROM open_tabs ORDER BY tab_order")
            .fetchall()
        )
        return [(row[0], bool(row[1])) for row in rows]
