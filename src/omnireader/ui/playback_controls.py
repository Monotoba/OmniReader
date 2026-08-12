from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QWidget,
)


class PlaybackControls(QWidget):
    play_requested = Signal()
    pause_requested = Signal()
    stop_requested = Signal()
    previous_requested = Signal()
    next_requested = Signal()
    previous_paragraph_requested = Signal()
    next_paragraph_requested = Signal()
    bookmark_requested = Signal()
    preferences_changed = Signal(str, str, float, float)
    reset_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.previous_paragraph = self._button(
            "⏮", "Previous paragraph", self.previous_paragraph_requested
        )
        self.previous = self._button("◀", "Previous sentence", self.previous_requested)
        self.play = self._button("▶", "Play", self.play_requested)
        self.pause = self._button("⏸", "Pause", self.pause_requested)
        self.stop = self._button("■", "Stop", self.stop_requested)
        self.next = self._button("▶|", "Next sentence", self.next_requested)
        self.next_paragraph = self._button(
            "⏭", "Next paragraph", self.next_paragraph_requested
        )
        for button in (
            self.previous_paragraph,
            self.previous,
            self.play,
            self.pause,
            self.stop,
            self.next,
            self.next_paragraph,
        ):
            layout.addWidget(button)
        layout.addSpacing(12)
        layout.addWidget(QLabel("Backend"))
        self.backend = QComboBox()
        self.backend.addItems(["edge", "piper"])
        layout.addWidget(self.backend)
        layout.addWidget(QLabel("Voice"))
        self.voice = QComboBox()
        self.voice.setEditable(True)
        self.voice.setMinimumWidth(180)
        layout.addWidget(self.voice, 1)
        layout.addWidget(QLabel("Rate"))
        self.rate = QDoubleSpinBox()
        self.rate.setRange(0.5, 2.0)
        self.rate.setSingleStep(0.1)
        self.rate.setValue(1.0)
        layout.addWidget(self.rate)
        layout.addWidget(QLabel("Pitch"))
        self.pitch = QDoubleSpinBox()
        self.pitch.setRange(-1.0, 1.0)
        self.pitch.setSingleStep(0.1)
        layout.addWidget(self.pitch)
        reset = QPushButton("Use global")
        reset.clicked.connect(self.reset_requested)
        layout.addWidget(reset)
        bookmark = QPushButton("Bookmark")
        bookmark.clicked.connect(self.bookmark_requested)
        layout.addWidget(bookmark)
        self.backend.currentTextChanged.connect(self._emit_preferences)
        self.voice.currentTextChanged.connect(self._emit_preferences)
        self.rate.valueChanged.connect(self._emit_preferences)
        self.pitch.valueChanged.connect(self._emit_preferences)

    @staticmethod
    def _button(text: str, tooltip: str, signal: Signal) -> QToolButton:
        button = QToolButton()
        button.setText(text)
        button.setToolTip(tooltip)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.clicked.connect(signal)
        return button

    def set_preferences(
        self, backend: str, voice: str, rate: float, pitch: float
    ) -> None:
        widgets = (self.backend, self.voice, self.rate, self.pitch)
        for widget in widgets:
            widget.blockSignals(True)
        self.backend.setCurrentText(backend)
        self.voice.clear()
        self.voice.addItem(voice)
        self.rate.setValue(rate)
        self.pitch.setValue(pitch)
        for widget in widgets:
            widget.blockSignals(False)

    def set_voices(self, values: list[tuple[str, str]], current: str) -> None:
        self.voice.blockSignals(True)
        self.voice.clear()
        for voice_id, name in values:
            self.voice.addItem(name, voice_id)
        index = self.voice.findData(current)
        if index >= 0:
            self.voice.setCurrentIndex(index)
        elif current:
            self.voice.addItem(current, current)
            self.voice.setCurrentIndex(self.voice.count() - 1)
        self.voice.blockSignals(False)

    def voice_id(self) -> str:
        return str(self.voice.currentData() or self.voice.currentText())

    def _emit_preferences(self, *_args) -> None:
        self.preferences_changed.emit(
            self.backend.currentText(),
            self.voice_id(),
            self.rate.value(),
            self.pitch.value(),
        )
