from pathlib import Path

from PySide6.QtCore import QObject, Signal

import omnireader.playback.engine as engine_module
from omnireader.document.parsers.registry import default_registry
from omnireader.persistence.bookmarks_repo import BookmarksRepository
from omnireader.persistence.db import Database
from omnireader.persistence.documents_repo import DocumentsRepository
from omnireader.persistence.settings_repo import SettingsRepository
from omnireader.tts.cache import AudioCache
from omnireader.ui.main_window import MainWindow


class FakeAudioPlayer(QObject):
    position_changed = Signal(int)
    finished = Signal()
    error = Signal(str)

    def play(self, _path: Path) -> None:
        pass

    def resume(self) -> None:
        pass

    def pause(self) -> None:
        pass

    def stop(self) -> None:
        pass


def test_main_window_opens_document_and_persists_tab(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("OMNIREADER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(engine_module, "AudioPlayer", FakeAudioPlayer)
    source = tmp_path / "book.txt"
    source.write_text("A sentence. Another sentence.", encoding="utf-8")
    database = Database(tmp_path / "library.db")
    documents = DocumentsRepository(database)
    window = MainWindow(
        default_registry(),
        documents,
        BookmarksRepository(database),
        SettingsRepository(database),
        AudioCache(tmp_path / "cache"),
    )
    qtbot.addWidget(window)

    window.open_paths([source])

    assert window.tabs.count() == 1
    assert window.current_reader().document.title == "book"
    window.close()
    assert len(documents.open_tabs()) == 1
