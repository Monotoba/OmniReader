from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer


class AudioPlayer(QObject):
    position_changed = Signal(object)
    finished = Signal()
    error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.output = QAudioOutput(self)
        self.player = QMediaPlayer(self)
        self.player.setAudioOutput(self.output)
        # Qt exposes this value as qlonglong. Connecting that signal directly
        # to Signal(int) is rejected by some PySide6 releases even though the
        # Python value is an int, so adapt it through a normal callable.
        self.player.positionChanged.connect(self._position_changed)
        self.player.mediaStatusChanged.connect(self._status_changed)
        self.player.errorOccurred.connect(
            lambda _code, message: self.error.emit(message)
        )

    def play(self, path: Path) -> None:
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.player.play()

    def resume(self) -> None:
        self.player.play()

    def pause(self) -> None:
        self.player.pause()

    def stop(self) -> None:
        self.player.stop()

    def _position_changed(self, position: int) -> None:
        self.position_changed.emit(int(position))

    def _status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.finished.emit()
