from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QInputDialog,
    QMessageBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..config import piper_voices_dir
from ..document.filters import FilterSettings
from ..document.model import NormalizedDocument, TextPosition
from ..persistence.bookmarks_repo import BookmarksRepository
from ..persistence.documents_repo import (
    DocumentsRepository,
    ReadingState,
    VoicePreferences,
)
from ..persistence.settings_repo import SettingsRepository
from ..playback.engine import PlaybackEngine, PlaybackPreferences
from ..tts.backend_manager import BackendManager
from ..tts.cache import AudioCache
from ..tts.edge_backend import EdgeTTSBackend
from ..tts.piper_backend import PiperTTSBackend
from .bookmark_panel import BookmarkPanel
from .document_view import DocumentView
from .filter_panel import FilterPanel
from .playback_controls import PlaybackControls


class ReaderTab(QWidget):
    play_started = Signal(object)
    status_message = Signal(str)

    def __init__(
        self,
        document: NormalizedDocument,
        path: Path,
        documents: DocumentsRepository,
        bookmarks: BookmarksRepository,
        settings: SettingsRepository,
        cache: AudioCache,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.document = document
        self.path = path
        self.documents = documents
        self.bookmarks = bookmarks
        self.settings = settings
        self.cache = cache
        self.documents.remember(document, path)
        filters = self.documents.filters(document.doc_id) or self._global_filters()
        prefs = self._resolved_preferences()
        models = Path(
            str(settings.get("tts.piper_models_dir", str(piper_voices_dir())))
        )
        manager = BackendManager(
            [
                EdgeTTSBackend(),
                PiperTTSBackend(models, bool(settings.get("tts.forced_alignment"))),
            ],
            cache,
        )
        manager.backend_changed.connect(
            lambda name, reason: self.status_message.emit(
                f"Using {name.title()} TTS ({reason})"
            )
        )
        manager.backend_unavailable.connect(
            lambda name: self.status_message.emit(
                f"{name.title()} TTS unavailable — using fallback"
            )
        )
        manager.preferred_available.connect(
            lambda name: self.status_message.emit(
                f"{name.title()} TTS is available again — select it to switch"
            )
        )
        self.manager = manager
        self.engine = PlaybackEngine(document, manager, filters, prefs, self)
        self.engine.error.connect(self._error)
        self.engine.position_changed.connect(lambda _position: self.save_state())
        self.engine.highlight_changed.connect(self._highlight)
        self.controls = PlaybackControls()
        self.controls.set_preferences(
            prefs.backend,
            (prefs.voices or {}).get(prefs.backend, ""),
            prefs.rate,
            prefs.pitch,
        )
        self.controls.play_requested.connect(self._play)
        self.controls.pause_requested.connect(self._pause)
        self.controls.stop_requested.connect(self._stop)
        self.controls.previous_requested.connect(self.engine.previous_sentence)
        self.controls.next_requested.connect(self.engine.next_sentence)
        self.controls.previous_paragraph_requested.connect(
            self.engine.previous_paragraph
        )
        self.controls.next_paragraph_requested.connect(self.engine.next_paragraph)
        self.controls.bookmark_requested.connect(self._add_bookmark)
        self.controls.preferences_changed.connect(self._preferences_changed)
        self.controls.reset_requested.connect(self._reset_preferences)
        self.view = DocumentView(document)
        font = QFont(str(settings.get("reading.font_family")))
        font.setPointSize(int(settings.get("reading.font_size")))
        self.view.setFont(font)
        self.view.apply_filters(filters)
        self.view.position_clicked.connect(self.engine.seek)
        self.filter_panel = FilterPanel(filters)
        self.filter_panel.filters_changed.connect(self._filters_changed)
        self.bookmark_panel = BookmarkPanel()
        self.bookmark_panel.bookmark_selected.connect(self.engine.seek)
        self.bookmark_panel.delete_requested.connect(self._delete_bookmark)
        self._refresh_bookmarks()
        side = QWidget()
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.addWidget(self.filter_panel)
        side_layout.addWidget(self.bookmark_panel, 1)
        splitter = QSplitter()
        splitter.addWidget(self.view)
        splitter.addWidget(side)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        layout = QVBoxLayout(self)
        layout.addWidget(self.controls)
        layout.addWidget(splitter, 1)
        self.autosave = QTimer(self)
        self.autosave.setInterval(15_000)
        self.autosave.timeout.connect(self.save_state)
        self.autosave.start()
        self.reprobe = QTimer(self)
        self.reprobe.setInterval(30_000)
        self.reprobe.timeout.connect(
            lambda: self.manager.probe_preferred(self.engine.preferences.backend)
        )
        self.reprobe.start()
        saved = self.documents.position(document.doc_id)
        if saved:
            self.engine.seek(saved.position)
            self.view.jump_to(saved.position)
            self.view.verticalScrollBar().setValue(saved.scroll_offset)

    def _global_filters(self) -> FilterSettings:
        return FilterSettings(
            **{
                name: bool(self.settings.get(f"filters.{name}"))
                for name in FilterSettings.__dataclass_fields__
            }
        )

    def _resolved_preferences(self) -> PlaybackPreferences:
        stored = (
            self.documents.voice_preferences(self.document.doc_id) or VoicePreferences()
        )
        backend = stored.backend_name or str(self.settings.get("tts.backend"))
        voice = stored.voice_id or str(self.settings.get(f"tts.voice.{backend}", ""))
        return PlaybackPreferences(
            backend,
            {
                backend: voice,
                "edge": str(self.settings.get("tts.voice.edge", "")),
                "piper": str(self.settings.get("tts.voice.piper", "")),
            },
            stored.rate
            if stored.rate is not None
            else float(self.settings.get("tts.rate")),
            stored.pitch
            if stored.pitch is not None
            else float(self.settings.get("tts.pitch")),
            int(self.settings.get("tts.buffer_depth")),
        )

    def _play(self) -> None:
        self.play_started.emit(self)
        self.engine.play()

    def _pause(self) -> None:
        self.engine.pause()
        self.save_state()

    def _stop(self) -> None:
        self.engine.stop()
        self.save_state()

    def pause_for_other_tab(self) -> None:
        self._pause()

    def _preferences_changed(
        self, backend: str, voice: str, rate: float, pitch: float
    ) -> None:
        voices = dict(self.engine.preferences.voices or {})
        voices[backend] = voice
        preferences = PlaybackPreferences(
            backend, voices, rate, pitch, int(self.settings.get("tts.buffer_depth"))
        )
        self.engine.set_preferences(preferences)
        self.documents.save_voice_preferences(
            self.document.doc_id, VoicePreferences(backend, voice, rate, pitch)
        )
        if backend == "piper":
            try:
                values = [(item.id, item.name) for item in self.manager.voices(backend)]
                self.controls.set_voices(values, voice)
            except Exception as exc:
                self.status_message.emit(str(exc))

    def _reset_preferences(self) -> None:
        preferences = PlaybackPreferences(
            str(self.settings.get("tts.backend")),
            {
                "edge": str(self.settings.get("tts.voice.edge", "")),
                "piper": str(self.settings.get("tts.voice.piper", "")),
            },
            float(self.settings.get("tts.rate")),
            float(self.settings.get("tts.pitch")),
            int(self.settings.get("tts.buffer_depth")),
        )
        self.documents.save_voice_preferences(self.document.doc_id, VoicePreferences())
        self.engine.set_preferences(preferences)
        self.controls.set_preferences(
            preferences.backend,
            (preferences.voices or {}).get(preferences.backend, ""),
            preferences.rate,
            preferences.pitch,
        )

    def _filters_changed(self, filters: FilterSettings) -> None:
        self.documents.save_filters(self.document.doc_id, filters)
        self.view.apply_filters(filters)
        self.engine.set_filters(filters)

    def _highlight(
        self, position: TextPosition, word_index: int, _sentence_only: bool
    ) -> None:
        self.view.highlight(
            position,
            word_index,
            str(self.settings.get("reading.sentence_color")),
            str(self.settings.get("reading.word_color")),
            bool(self.settings.get("reading.auto_scroll")),
        )

    def _add_bookmark(self) -> None:
        position = self.engine.position
        if not position:
            return
        label, accepted = QInputDialog.getText(self, "Add bookmark", "Label")
        if accepted:
            self.bookmarks.add(self.document.doc_id, position, label)
            self._refresh_bookmarks()

    def _delete_bookmark(self, bookmark_id: int) -> None:
        self.bookmarks.delete(bookmark_id)
        self._refresh_bookmarks()

    def _refresh_bookmarks(self) -> None:
        self.bookmark_panel.set_bookmarks(self.bookmarks.list_for(self.document.doc_id))

    def _error(self, message: str) -> None:
        QMessageBox.warning(self, "Playback error", message)

    def save_state(self) -> None:
        position = self.engine.position
        if position:
            self.documents.save_position(
                self.document.doc_id,
                ReadingState(
                    position.block_id,
                    position.sentence_index,
                    position.word_index,
                    self.view.verticalScrollBar().value(),
                ),
            )

    def shutdown(self) -> None:
        self.save_state()
        self.engine.stop()
