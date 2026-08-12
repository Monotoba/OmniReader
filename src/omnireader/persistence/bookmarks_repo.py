from __future__ import annotations

from dataclasses import dataclass

from ..document.model import TextPosition
from .db import Database


@dataclass(frozen=True, slots=True)
class Bookmark:
    id: int
    doc_id: str
    position: TextPosition
    label: str
    note: str
    created_at: str


class BookmarksRepository:
    def __init__(self, database: Database) -> None:
        self.db = database

    def add(
        self, doc_id: str, position: TextPosition, label: str, note: str = ""
    ) -> Bookmark:
        clean_label = label.strip() or "Bookmark"
        with self.db.transaction() as connection:
            cursor = connection.execute(
                """INSERT INTO bookmarks
                   (doc_id, block_id, sentence_index, word_index, label, note)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    doc_id,
                    position.block_id,
                    position.sentence_index,
                    position.word_index,
                    clean_label,
                    note.strip(),
                ),
            )
            if cursor.lastrowid is None:
                raise RuntimeError("SQLite did not return a bookmark id")
            bookmark_id = cursor.lastrowid
        return self.get(bookmark_id)

    def get(self, bookmark_id: int) -> Bookmark:
        row = (
            self.db.connection()
            .execute("SELECT * FROM bookmarks WHERE id = ?", (bookmark_id,))
            .fetchone()
        )
        if not row:
            raise KeyError(bookmark_id)
        return Bookmark(
            row["id"],
            row["doc_id"],
            TextPosition(row["block_id"], row["sentence_index"], row["word_index"]),
            row["label"],
            row["note"],
            row["created_at"],
        )

    def list_for(self, doc_id: str) -> list[Bookmark]:
        rows = (
            self.db.connection()
            .execute(
                "SELECT id FROM bookmarks WHERE doc_id = ? ORDER BY created_at, id",
                (doc_id,),
            )
            .fetchall()
        )
        return [self.get(row[0]) for row in rows]

    def delete(self, bookmark_id: int) -> None:
        with self.db.transaction() as connection:
            connection.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,))
