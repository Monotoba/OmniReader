from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor, QTextFormat
from PySide6.QtWidgets import QTextBrowser, QTextEdit

from ..document.filters import FilterSettings
from ..document.model import NormalizedDocument, TextPosition
from ..playback.highlight_sync import resolve_highlight


class DocumentView(QTextBrowser):
    position_clicked = Signal(object)

    def __init__(self, document: NormalizedDocument, parent=None) -> None:
        super().__init__(parent)
        self.normalized_document = document
        self.setOpenLinks(False)
        self.setReadOnly(True)
        self._offsets: dict[str, int] = {}
        self._render(FilterSettings())

    def _render(self, filters: FilterSettings) -> None:
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.removeSelectedText()
        self._offsets.clear()
        for index, block in enumerate(self.normalized_document.blocks):
            if index:
                cursor.insertText("\n\n")
            self._offsets[block.id] = cursor.position()
            block_format = QTextCharFormat()
            if block.kind == "heading":
                block_format.setFontWeight(700)
                block_format.setFontPointSize(self.font().pointSizeF() + 3)
            if filters.excludes(block):
                block_format.setForeground(QColor("#888888"))
            cursor.insertText(block.plain_text, block_format)
        self.setTextCursor(cursor)

    def apply_filters(self, filters: FilterSettings) -> None:
        scroll = self.verticalScrollBar().value()
        self._render(filters)
        self.verticalScrollBar().setValue(scroll)

    def highlight(
        self,
        position: TextPosition,
        word_index: int,
        sentence_color: str,
        word_color: str,
        auto_scroll: bool,
    ) -> None:
        span = resolve_highlight(self.normalized_document, position, word_index)
        if not span or span.block_id not in self._offsets:
            return
        base = self._offsets[span.block_id]
        selections: list[QTextEdit.ExtraSelection] = []
        sentence = QTextEdit.ExtraSelection()
        sentence.cursor = self.textCursor()
        sentence.cursor.setPosition(base + span.sentence_start)
        sentence.cursor.setPosition(
            base + span.sentence_end, QTextCursor.MoveMode.KeepAnchor
        )
        sentence.format.setBackground(QColor(sentence_color))
        sentence.format.setProperty(QTextFormat.Property.FullWidthSelection, False)
        selections.append(sentence)
        if span.word_start is not None and span.word_end is not None:
            word = QTextEdit.ExtraSelection()
            word.cursor = self.textCursor()
            word.cursor.setPosition(base + span.word_start)
            word.cursor.setPosition(
                base + span.word_end, QTextCursor.MoveMode.KeepAnchor
            )
            word.format.setBackground(QColor(word_color))
            selections.append(word)
        self.setExtraSelections(selections)
        if auto_scroll:
            self.setTextCursor(sentence.cursor)
            self.ensureCursorVisible()

    def jump_to(self, position: TextPosition) -> None:
        block = self.normalized_document.block(position.block_id)
        if not block or position.block_id not in self._offsets:
            return
        sentence_index = min(position.sentence_index, max(0, len(block.sentences) - 1))
        offset = block.sentences[sentence_index].char_start if block.sentences else 0
        cursor = self.textCursor()
        cursor.setPosition(self._offsets[position.block_id] + offset)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        cursor_position = self.cursorForPosition(event.position().toPoint()).position()
        for block in self.normalized_document.blocks:
            start = self._offsets.get(block.id)
            if start is None or not (
                start <= cursor_position <= start + len(block.plain_text)
            ):
                continue
            local = cursor_position - start
            for sentence_index, sentence in enumerate(block.sentences):
                if sentence.char_start <= local <= sentence.char_end:
                    word_index = 0
                    for index, word in enumerate(sentence.words):
                        if word.char_start <= local:
                            word_index = index
                    self.position_clicked.emit(
                        TextPosition(block.id, sentence_index, word_index)
                    )
                    return
