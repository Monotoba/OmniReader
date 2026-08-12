from __future__ import annotations

from PySide6.QtCore import QObject, Signal

import omnireader.playback.audio_player as audio_player_module


class FakeAudioOutput(QObject):
    pass


class FakeMediaPlayer(QObject):
    """Expose the same 64-bit position signal that triggered the PySide error."""

    positionChanged = Signal("qlonglong")
    mediaStatusChanged = Signal(object)
    errorOccurred = Signal(object, str)

    class MediaStatus:
        EndOfMedia = object()

    def setAudioOutput(self, _output: QObject) -> None:
        pass

    def setSource(self, _source: object) -> None:
        pass

    def play(self) -> None:
        pass

    def pause(self) -> None:
        pass

    def stop(self) -> None:
        pass


def test_audio_player_adapts_qt_64_bit_position_signal(monkeypatch) -> None:
    monkeypatch.setattr(audio_player_module, "QAudioOutput", FakeAudioOutput)
    monkeypatch.setattr(audio_player_module, "QMediaPlayer", FakeMediaPlayer)

    player = audio_player_module.AudioPlayer()
    positions: list[int] = []
    player.position_changed.connect(positions.append)

    player.player.positionChanged.emit(2**32)

    assert positions == [2**32]
