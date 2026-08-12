from pathlib import Path

from omnireader.document.model import TextPosition
from omnireader.playback.playback_clock import PlaybackClock
from omnireader.tts.alignment import estimated_word_timings
from omnireader.tts.base import SynthesisResult, TextChunk, WordTiming
from omnireader.tts.cache import AudioCache


def test_estimated_timings_cover_duration_and_clock_uses_boundaries() -> None:
    timings = estimated_word_timings(("Hi", "everyone."), 1_000)
    clock = PlaybackClock(timings)

    assert timings[0].start_ms == 0
    assert timings[-1].end_ms == 1_000
    assert clock.word_at(timings[1].start_ms) == 1
    assert clock.word_at(1_001) is None


def test_audio_cache_round_trip(tmp_path: Path) -> None:
    cache = AudioCache(tmp_path / "cache")
    source = tmp_path / "audio.mp3"
    source.write_bytes(b"audio")
    chunk = TextChunk("Hello", TextPosition("p"), ("Hello",))
    key = cache.key("test", chunk, "voice", 1.0, 0.0)
    expected = SynthesisResult(source, (WordTiming(0, 0, 10),), False)

    stored = cache.put(key, expected)
    loaded = cache.get(key)

    assert stored.audio_path.exists()
    assert loaded == stored
