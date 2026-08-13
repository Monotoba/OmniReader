from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import QProcess

from omnireader.playback.audio_player import AudioPlayer


def test_audio_player_prefers_ffplay(monkeypatch) -> None:
    monkeypatch.setattr(
        shutil, "which", lambda name: "/usr/bin/ffplay" if name == "ffplay" else None
    )

    player = AudioPlayer()

    assert player._program == Path("/usr/bin/ffplay")
    assert player._process.processEnvironment().value("SDL_AUDIODRIVER") == "pulseaudio"


def test_audio_player_reports_missing_external_player(monkeypatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    player = AudioPlayer()
    errors: list[str] = []
    player.error.connect(errors.append)

    player.play(Path("missing.mp3"))

    assert errors and "ffplay" in errors[0] and "mpv" in errors[0]


def test_audio_player_tracks_position_without_qt_multimedia(monkeypatch) -> None:
    monkeypatch.setattr(
        shutil, "which", lambda name: "/usr/bin/ffplay" if name == "ffplay" else None
    )
    player = AudioPlayer()
    positions: list[int] = []
    player.position_changed.connect(positions.append)
    player._elapsed_ms = 123
    player._started_at = None

    player._emit_position()

    assert positions == [123]
    assert player._process.state() == QProcess.ProcessState.NotRunning
