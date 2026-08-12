from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..persistence.bookmarks_repo import Bookmark


class BookmarkPanel(QWidget):
    bookmark_selected = Signal(object)
    delete_requested = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.list = QListWidget()
        self.list.itemActivated.connect(self._activated)
        layout.addWidget(self.list)
        delete = QPushButton("Delete selected")
        delete.clicked.connect(self._delete)
        layout.addWidget(delete)

    def set_bookmarks(self, bookmarks: list[Bookmark]) -> None:
        self.list.clear()
        for bookmark in bookmarks:
            item = QListWidgetItem(bookmark.label)
            item.setToolTip(bookmark.note)
            item.setData(256, bookmark)
            self.list.addItem(item)

    def _activated(self, item: QListWidgetItem) -> None:
        bookmark = item.data(256)
        self.bookmark_selected.emit(bookmark.position)

    def _delete(self) -> None:
        item = self.list.currentItem()
        if item:
            self.delete_requested.emit(item.data(256).id)
