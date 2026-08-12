from pathlib import Path

from omnireader.document.model import TextPosition
from omnireader.tts.backend_manager import BackendManager
from omnireader.tts.base import (
    BackendUnavailableError,
    SynthesisResult,
    TextChunk,
    TTSBackend,
    VoiceInfo,
)
from omnireader.tts.cache import AudioCache


class FakeBackend(TTSBackend):
    requires_network = False

    def __init__(
        self, name: str, available: bool, output: Path, fail: bool = False
    ) -> None:
        self.name = name
        self.available = available
        self.output = output
        self.fail = fail

    def is_available(self) -> bool:
        return self.available

    def list_voices(self) -> list[VoiceInfo]:
        return [VoiceInfo("voice", "Voice")]

    def synthesize(self, text_chunk, voice_id, rate, pitch) -> SynthesisResult:
        if self.fail:
            raise BackendUnavailableError("failed")
        self.output.write_bytes(b"audio")
        return SynthesisResult(self.output)

    def cancel(self) -> None:
        pass


def test_manager_selects_available_fallback(tmp_path: Path) -> None:
    edge = FakeBackend("edge", False, tmp_path / "edge.mp3")
    piper = FakeBackend("piper", True, tmp_path / "piper.wav")
    manager = BackendManager([edge, piper], AudioCache(tmp_path / "cache"))
    chunk = TextChunk("Hello", TextPosition("p"), ("Hello",))

    result = manager.synthesize(chunk, "edge", {"piper": "voice"}, 1.0, 0.0)

    assert manager.active_name == "piper"
    assert result.audio_path.exists()
