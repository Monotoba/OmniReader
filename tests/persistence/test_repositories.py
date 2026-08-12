from pathlib import Path

from omnireader.document.filters import FilterSettings
from omnireader.document.model import NormalizedDocument, TextPosition
from omnireader.document.parsers.base import make_block
from omnireader.persistence.bookmarks_repo import BookmarksRepository
from omnireader.persistence.db import Database
from omnireader.persistence.documents_repo import (
    DocumentsRepository,
    ReadingState,
    VoicePreferences,
)
from omnireader.persistence.settings_repo import SettingsRepository


def test_repositories_round_trip_document_state(tmp_path: Path) -> None:
    source = tmp_path / "book.txt"
    source.write_text("Hello.", encoding="utf-8")
    document = NormalizedDocument("doc", "Book", (make_block("p", "Hello."),))
    database = Database(tmp_path / "library.db")
    documents = DocumentsRepository(database)
    bookmarks = BookmarksRepository(database)
    documents.remember(document, source)

    state = ReadingState("p", 0, 0, 42)
    voice = VoicePreferences("piper", "amy", 1.2, -0.1)
    filters = FilterSettings(skip_code=True)
    documents.save_position("doc", state)
    documents.save_voice_preferences("doc", voice)
    documents.save_filters("doc", filters)
    bookmark = bookmarks.add("doc", TextPosition("p"), "Start", "A note")
    documents.save_tabs([("doc", True)])

    assert documents.path_for("doc") == source
    assert documents.position("doc") == state
    assert documents.voice_preferences("doc") == voice
    assert documents.filters("doc") == filters
    assert bookmarks.list_for("doc") == [bookmark]
    assert documents.open_tabs() == [("doc", True)]
    bookmarks.delete(bookmark.id)
    assert bookmarks.list_for("doc") == []


def test_settings_use_defaults_and_json_round_trip(tmp_path: Path) -> None:
    settings = SettingsRepository(Database(tmp_path / "library.db"))

    assert settings.get("tts.rate") == 1.0
    settings.set("custom.value", {"enabled": True})
    assert settings.get("custom.value") == {"enabled": True}
