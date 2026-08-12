from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from ..document.model import TextPosition


class TTSError(RuntimeError):
    pass


class BackendUnavailableError(TTSError):
    pass


@dataclass(frozen=True, slots=True)
class VoiceInfo:
    id: str
    name: str
    locale: str = ""
    gender: str = ""


@dataclass(frozen=True, slots=True)
class WordTiming:
    word_index: int
    start_ms: int
    end_ms: int


@dataclass(frozen=True, slots=True)
class TextChunk:
    text: str
    position: TextPosition
    words: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SynthesisResult:
    audio_path: Path
    word_timings: tuple[WordTiming, ...] = ()
    sentence_only_timing: bool = False


class TTSBackend(ABC):
    name: str
    requires_network: bool

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def list_voices(self) -> list[VoiceInfo]:
        raise NotImplementedError

    @abstractmethod
    def synthesize(
        self, text_chunk: TextChunk, voice_id: str, rate: float, pitch: float
    ) -> SynthesisResult:
        raise NotImplementedError

    @abstractmethod
    def cancel(self) -> None:
        raise NotImplementedError


def percent_rate(rate: float) -> str:
    return f"{round((max(0.5, min(2.0, rate)) - 1.0) * 100):+d}%"


def hz_pitch(pitch: float) -> str:
    return f"{round(max(-1.0, min(1.0, pitch)) * 50):+d}Hz"
