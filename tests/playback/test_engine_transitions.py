from __future__ import annotations

import threading
import time
from pathlib import Path

from PySide6.QtCore import QObject, Signal

import omnireader.playback.engine as engine_module
from omnireader.document.filters import FilterSettings
from omnireader.document.model import NormalizedDocument
from omnireader.document.parsers.base import make_block
from omnireader.playback.engine import PlaybackEngine, PlaybackPreferences
from omnireader.tts.base import SynthesisResult


class FakeAudioPlayer(QObject):
    position_changed = Signal(int)
    finished = Signal()
    error = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.played: list[Path] = []

    def play(self, path: Path) -> None:
        self.played.append(path)

    def resume(self) -> None:
        pass

    def pause(self) -> None:
        pass

    def stop(self) -> None:
        pass


class RecordingManager:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.calls: list[str] = []
        self.cancel_count = 0
        self.active = 0
        self.max_active = 0
        self._lock = threading.Lock()

    def synthesize(
        self, chunk, preferred, voices, rate, pitch, cancellation=None
    ) -> SynthesisResult:
        del chunk, voices, rate, pitch
        with self._lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        try:
            time.sleep(0.05)
            self.calls.append(preferred)
            path = self.directory / f"{preferred}-{len(self.calls)}.mp3"
            path.write_bytes(b"audio")
            return SynthesisResult(path)
        finally:
            with self._lock:
                self.active -= 1

    def cancel(self) -> None:
        self.cancel_count += 1


def test_repeated_play_and_backend_switches_serialize_and_drop_stale_work(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(engine_module, "AudioPlayer", FakeAudioPlayer)
    document = NormalizedDocument(
        "doc",
        "Document",
        (make_block("p", "One sentence. Two sentence. Three sentence."),),
    )
    manager = RecordingManager(tmp_path)
    engine = PlaybackEngine(
        document,
        manager,  # type: ignore[arg-type]
        FilterSettings(),
        PlaybackPreferences("edge", {"edge": "edge-voice", "piper": "model"}),
    )

    engine.play()
    engine.play()
    engine.set_preferences(
        PlaybackPreferences("piper", {"edge": "edge-voice", "piper": "model"})
    )
    engine.play()
    engine.set_preferences(
        PlaybackPreferences("edge", {"edge": "edge-voice", "piper": "model"})
    )
    engine.play()

    qtbot.waitUntil(lambda: len(engine._buffer) == 3, timeout=5_000)

    assert engine.preferences.backend == "edge"
    assert manager.max_active == 1
    assert manager.cancel_count == 2
    assert all(
        result.audio_path.name.startswith("edge-") for result in engine._buffer.values()
    )
    qtbot.waitUntil(lambda: not engine._workers, timeout=2_000)
