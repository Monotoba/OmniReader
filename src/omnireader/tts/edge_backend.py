from __future__ import annotations

import asyncio
import socket
import tempfile
import threading
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, TypeVar

from .base import (
    BackendUnavailableError,
    SynthesisResult,
    TextChunk,
    TTSBackend,
    VoiceInfo,
    WordTiming,
    hz_pitch,
    percent_rate,
)


class EdgeTTSBackend(TTSBackend):
    name = "edge"
    requires_network = True

    def __init__(self) -> None:
        self._cancelled = threading.Event()

    def is_available(self) -> bool:
        try:
            with socket.create_connection(
                ("speech.platform.bing.com", 443), timeout=1.5
            ):
                return True
        except OSError:
            return False

    def list_voices(self) -> list[VoiceInfo]:
        try:
            import edge_tts

            values = _run_async(edge_tts.list_voices())
            return [
                VoiceInfo(
                    item["ShortName"],
                    item["FriendlyName"],
                    item["Locale"],
                    item["Gender"],
                )
                for item in values
            ]
        except Exception as exc:
            raise BackendUnavailableError(f"Could not load Edge voices: {exc}") from exc

    async def _synthesize(
        self, chunk: TextChunk, voice_id: str, rate: float, pitch: float, path: Path
    ) -> tuple[WordTiming, ...]:
        try:
            import edge_tts
        except ImportError as exc:
            raise BackendUnavailableError("Edge TTS support requires edge-tts") from exc
        communicate = edge_tts.Communicate(
            chunk.text, voice_id, rate=percent_rate(rate), pitch=hz_pitch(pitch)
        )
        timings: list[WordTiming] = []
        word_index = 0
        with path.open("wb") as audio:
            async for event in communicate.stream():
                if self._cancelled.is_set():
                    raise BackendUnavailableError("Edge synthesis was cancelled")
                if event["type"] == "audio":
                    audio.write(event["data"])
                elif event["type"] == "WordBoundary":
                    start = int(event["offset"] / 10_000)
                    duration = int(event["duration"] / 10_000)
                    timings.append(
                        WordTiming(word_index, start, start + max(duration, 1))
                    )
                    word_index += 1
        return tuple(timings)

    def synthesize(
        self, text_chunk: TextChunk, voice_id: str, rate: float, pitch: float
    ) -> SynthesisResult:
        self._cancelled.clear()
        handle, name = tempfile.mkstemp(prefix="omnireader-edge-", suffix=".mp3")
        import os

        os.close(handle)
        path = Path(name)
        try:
            timings = _run_async(
                self._synthesize(text_chunk, voice_id, rate, pitch, path)
            )
            return SynthesisResult(path, timings, False)
        except BackendUnavailableError:
            path.unlink(missing_ok=True)
            raise
        except Exception as exc:
            path.unlink(missing_ok=True)
            raise BackendUnavailableError(f"Edge synthesis failed: {exc}") from exc

    def cancel(self) -> None:
        self._cancelled.set()


T = TypeVar("T")


def _run_async(coroutine: Coroutine[Any, Any, T]) -> T:
    """Run edge-tts in a synthesis worker, including when a loop already exists."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    result: list[T] = []
    error: list[BaseException] = []

    def runner() -> None:
        try:
            result.append(asyncio.run(coroutine))
        except BaseException as exc:
            error.append(exc)

    thread = threading.Thread(target=runner)
    thread.start()
    thread.join()
    if error:
        raise error[0]
    return result[0]
