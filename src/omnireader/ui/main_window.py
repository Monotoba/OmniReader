from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDragEnterEvent,
    QDropEvent,
    QKeySequence,
    QMouseEvent,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QToolButton,
)

from ..document.parsers import ParserRegistry
from ..document.parsers.base import DocumentParseError
from ..persistence.bookmarks_repo import BookmarksRepository
from ..persistence.documents_repo import DocumentsRepository
from ..persistence.settings_repo import SettingsRepository
from ..tts.cache import AudioCache
from .reader_tab import ReaderTab
from .settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    def __init__(
        self,
        registry: ParserRegistry,
        documents: DocumentsRepository,
        bookmarks: BookmarksRepository,
        settings: SettingsRepository,
        cache: AudioCache,
    ) -> None:
        super().__init__()
        self.registry = registry
        self.documents = documents
        self.bookmarks = bookmarks
        self.settings = settings
        self.cache = cache
        self.setWindowTitle("OmniReader")
        self.resize(1200, 780)
        self.setAcceptDrops(True)
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self._tab_changed)
        self.tabs.tabBar().installEventFilter(self)
        plus = QToolButton()
        plus.setText("+")
        plus.setToolTip("Open documents")
        plus.clicked.connect(self.open_dialog)
        self.tabs.setCornerWidget(plus)
        self.setCentralWidget(self.tabs)
        self._create_actions()

    def _create_actions(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        open_action = QAction("&Open…", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self.open_dialog)
        file_menu.addAction(open_action)
        close_action = QAction("Close tab", self)
        close_action.setShortcut(QKeySequence.StandardKey.Close)
        close_action.triggered.connect(lambda: self.close_tab(self.tabs.currentIndex()))
        file_menu.addAction(close_action)
        file_menu.addSeparator()
        settings_action = QAction("&Settings…", self)
        settings_action.triggered.connect(self.open_settings)
        file_menu.addAction(settings_action)
        file_menu.addSeparator()
        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)
        playback_menu = self.menuBar().addMenu("&Playback")
        for text, shortcut, callback in (
            ("Play", "Space", lambda: self._current_call("_play")),
            ("Pause", "Ctrl+Space", lambda: self._current_call("_pause")),
            (
                "Previous sentence",
                "Alt+Left",
                lambda: self._engine_call("previous_sentence"),
            ),
            ("Next sentence", "Alt+Right", lambda: self._engine_call("next_sentence")),
            ("Add bookmark", "Ctrl+B", lambda: self._current_call("_add_bookmark")),
        ):
            action = QAction(text, self)
            action.setShortcut(shortcut)
            action.triggered.connect(callback)
            playback_menu.addAction(action)

    def current_reader(self) -> ReaderTab | None:
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, ReaderTab) else None

    def _current_call(self, name: str) -> None:
        tab = self.current_reader()
        if tab:
            getattr(tab, name)()

    def _engine_call(self, name: str) -> None:
        tab = self.current_reader()
        if tab:
            getattr(tab.engine, name)()

    def open_dialog(self) -> None:
        extensions = " ".join(
            f"*{value}" for value in self.registry.supported_extensions
        )
        paths, _selected = QFileDialog.getOpenFileNames(
            self,
            "Open documents",
            str(Path.home()),
            f"Documents ({extensions});;All files (*)",
        )
        self.open_paths([Path(path) for path in paths])

    def open_paths(self, paths: list[Path]) -> None:
        for path in paths:
            try:
                document = self.registry.parse(path)
            except (DocumentParseError, OSError) as exc:
                QMessageBox.warning(
                    self, "Could not open document", f"{path.name}: {exc}"
                )
                continue
            existing = next(
                (
                    index
                    for index in range(self.tabs.count())
                    if isinstance(self.tabs.widget(index), ReaderTab)
                    and self.tabs.widget(index).document.doc_id == document.doc_id
                ),
                None,
            )
            if existing is not None:
                self.tabs.setCurrentIndex(existing)
                continue
            tab = ReaderTab(
                document,
                path.resolve(),
                self.documents,
                self.bookmarks,
                self.settings,
                self.cache,
            )
            tab.play_started.connect(self._pause_other_tabs)
            tab.status_message.connect(
                lambda message: self.statusBar().showMessage(message, 7000)
            )
            index = self.tabs.addTab(tab, document.title)
            self.tabs.setTabToolTip(index, str(path))
            self.tabs.setCurrentIndex(index)

    def restore_session(self) -> None:
        if not self.settings.get("reading.reopen_tabs"):
            return
        active_id = None
        for doc_id, active in self.documents.open_tabs():
            path = self.documents.path_for(doc_id)
            if path and path.is_file():
                self.open_paths([path])
                if active:
                    active_id = doc_id
        if active_id:
            for index in range(self.tabs.count()):
                tab = self.tabs.widget(index)
                if isinstance(tab, ReaderTab) and tab.document.doc_id == active_id:
                    self.tabs.setCurrentIndex(index)
                    break

    def close_tab(self, index: int) -> None:
        if index < 0:
            return
        widget = self.tabs.widget(index)
        if isinstance(widget, ReaderTab):
            widget.shutdown()
        self.tabs.removeTab(index)
        widget.deleteLater()

    def _pause_other_tabs(self, active: ReaderTab) -> None:
        for index in range(self.tabs.count()):
            tab = self.tabs.widget(index)
            if isinstance(tab, ReaderTab) and tab is not active:
                tab.pause_for_other_tab()

    def _tab_changed(self, _index: int) -> None:
        for index in range(self.tabs.count()):
            tab = self.tabs.widget(index)
            if isinstance(tab, ReaderTab):
                tab.save_state()

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self.cache, self)
        if dialog.exec():
            self.statusBar().showMessage(
                "Settings saved; new defaults apply to new or reset tabs", 5000
            )

    def eventFilter(self, watched, event) -> bool:
        if (
            watched is self.tabs.tabBar()
            and event.type() == QEvent.Type.MouseButtonRelease
        ):
            mouse_event = event
            if (
                isinstance(mouse_event, QMouseEvent)
                and mouse_event.button() == Qt.MouseButton.MiddleButton
            ):
                self.close_tab(
                    self.tabs.tabBar().tabAt(mouse_event.position().toPoint())
                )
                return True
        return super().eventFilter(watched, event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls() and any(
            url.isLocalFile() for url in event.mimeData().urls()
        ):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        self.open_paths(
            [
                Path(url.toLocalFile())
                for url in event.mimeData().urls()
                if url.isLocalFile()
            ]
        )
        event.acceptProposedAction()

    def closeEvent(self, event: QCloseEvent) -> None:
        current = self.current_reader()
        tab_state = []
        for index in range(self.tabs.count()):
            tab = self.tabs.widget(index)
            if isinstance(tab, ReaderTab):
                tab.save_state()
                tab.engine.stop()
                tab_state.append((tab.document.doc_id, tab is current))
        self.documents.save_tabs(tab_state)
        event.accept()
