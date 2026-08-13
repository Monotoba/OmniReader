from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Signal

from .base import (
    BackendUnavailableError,
    SynthesisCancelledError,
    SynthesisResult,
    TextChunk,
    TTSBackend,
    VoiceInfo,
)
from .cache import AudioCache


class BackendManager(QObject):
    backend_changed = Signal(str, str)
    backend_unavailable = Signal(str)
    preferred_available = Signal(str)

    def __init__(self, backends: list[TTSBackend], cache: AudioCache) -> None:
        super().__init__()
        self.backends = {backend.name: backend for backend in backends}
        self.order = [backend.name for backend in backends]
        self.cache = cache
        self.active_name: str | None = None
        self._synthesis_lock = threading.Lock()

    def select(self, preferred: str) -> TTSBackend:
        order = [preferred, *(name for name in self.order if name != preferred)]
        for name in order:
            backend = self.backends.get(name)
            if backend and backend.is_available():
                if name != self.active_name:
                    reason = (
                        "preferred"
                        if name == preferred
                        else f"{preferred} unavailable; fallback"
                    )
                    self.active_name = name
                    self.backend_changed.emit(name, reason)
                if name != preferred:
                    self.backend_unavailable.emit(preferred)
                return backend
        raise BackendUnavailableError(
            "No configured text-to-speech backend is available"
        )

    def voices(self, backend_name: str) -> list[VoiceInfo]:
        backend = self.backends.get(backend_name)
        return backend.list_voices() if backend else []

    def synthesize(
        self,
        chunk: TextChunk,
        preferred: str,
        voice_by_backend: dict[str, str],
        rate: float,
        pitch: float,
        cancellation: threading.Event | None = None,
    ) -> SynthesisResult:
        # Backend implementations own mutable cancellation and subprocess
        # state. A manager deliberately exposes a single synthesis lane.
        with self._synthesis_lock:
            return self._synthesize(
                chunk, preferred, voice_by_backend, rate, pitch, cancellation
            )

    def _synthesize(
        self,
        chunk: TextChunk,
        preferred: str,
        voice_by_backend: dict[str, str],
        rate: float,
        pitch: float,
        cancellation: threading.Event | None,
    ) -> SynthesisResult:
        if cancellation and cancellation.is_set():
            raise SynthesisCancelledError("Synthesis was cancelled")
        attempted: set[str] = set()
        backend = self.select(preferred)
        while backend.name not in attempted:
            if cancellation and cancellation.is_set():
                raise SynthesisCancelledError("Synthesis was cancelled")
            attempted.add(backend.name)
            voice = voice_by_backend.get(backend.name, "")
            if not voice:
                voices = backend.list_voices()
                if not voices:
                    raise BackendUnavailableError(
                        f"No voices available for {backend.name}"
                    )
                voice = voices[0].id
            key = self.cache.key(backend.name, chunk, voice, rate, pitch)
            cached = self.cache.get(key)
            if cached:
                if cancellation and cancellation.is_set():
                    raise SynthesisCancelledError("Synthesis was cancelled")
                return cached
            try:
                result = backend.synthesize(chunk, voice, rate, pitch)
                if cancellation and cancellation.is_set():
                    result.audio_path.unlink(missing_ok=True)
                    raise SynthesisCancelledError("Synthesis was cancelled")
                return self.cache.put(key, result)
            except BackendUnavailableError as exc:
                if cancellation and cancellation.is_set():
                    raise SynthesisCancelledError("Synthesis was cancelled") from exc
                self.backend_unavailable.emit(backend.name)
                candidates = [
                    candidate
                    for candidate in self.order
                    if candidate not in attempted
                    and self.backends[candidate].is_available()
                ]
                if not candidates:
                    raise
                backend = self.backends[candidates[0]]
                self.active_name = backend.name
                self.backend_changed.emit(
                    backend.name, "fallback after synthesis failure"
                )
        raise BackendUnavailableError(
            "No text-to-speech backend could synthesize this text"
        )

    def cancel(self) -> None:
        for backend in self.backends.values():
            backend.cancel()

    def probe_preferred(self, preferred: str) -> None:
        backend = self.backends.get(preferred)
        if backend and preferred != self.active_name and backend.is_available():
            self.preferred_available.emit(preferred)
