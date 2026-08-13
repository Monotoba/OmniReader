from __future__ import annotations

import shutil
import subprocess
import tempfile
import threading
from pathlib import Path

from .alignment import audio_duration_ms, estimated_word_timings, forced_word_timings
from .base import (
    BackendUnavailableError,
    SynthesisCancelledError,
    SynthesisResult,
    TextChunk,
    TTSBackend,
    VoiceInfo,
)


class PiperTTSBackend(TTSBackend):
    name = "piper"
    requires_network = False

    def __init__(self, models_dir: Path, forced_alignment: bool = False) -> None:
        self.models_dir = models_dir.expanduser()
        self.forced_alignment = forced_alignment
        self._process: subprocess.Popen[bytes] | None = None
        self._lock = threading.Lock()
        self._cancelled = threading.Event()

    def _models(self) -> list[Path]:
        if not self.models_dir.is_dir():
            return []
        return sorted(
            model
            for model in self.models_dir.glob("*.onnx")
            if model.with_suffix(".onnx.json").is_file()
        )

    def is_available(self) -> bool:
        return bool(self._models()) and shutil.which("piper") is not None

    def list_voices(self) -> list[VoiceInfo]:
        return [VoiceInfo(str(model), model.stem) for model in self._models()]

    def synthesize(
        self, text_chunk: TextChunk, voice_id: str, rate: float, pitch: float
    ) -> SynthesisResult:
        del pitch  # Piper CLI models do not expose a portable pitch control.
        self._cancelled.clear()
        executable = shutil.which("piper")
        model = Path(voice_id).expanduser()
        if not executable or not model.is_file():
            raise BackendUnavailableError(
                "Piper executable or selected voice model is unavailable"
            )
        handle, name = tempfile.mkstemp(prefix="omnireader-piper-", suffix=".wav")
        import os

        os.close(handle)
        path = Path(name)
        command = [executable, "--model", str(model), "--output_file", str(path)]
        if rate != 1.0:
            command.extend(["--length_scale", str(1.0 / max(0.5, min(2.0, rate)))])
        try:
            with self._lock:
                process = subprocess.Popen(
                    command, stdin=subprocess.PIPE, stderr=subprocess.PIPE
                )
                self._process = process
            _stdout, stderr = process.communicate(
                text_chunk.text.encode("utf-8"), timeout=120
            )
            return_code = process.returncode
            with self._lock:
                if self._process is process:
                    self._process = None
            if self._cancelled.is_set():
                path.unlink(missing_ok=True)
                raise SynthesisCancelledError("Piper synthesis was cancelled")
            if return_code or not path.exists():
                raise BackendUnavailableError(
                    stderr.decode(errors="replace").strip() or "Piper failed"
                )
            aligned = (
                forced_word_timings(path, text_chunk.words)
                if self.forced_alignment
                else None
            )
            timings = aligned or estimated_word_timings(
                text_chunk.words, audio_duration_ms(path)
            )
            return SynthesisResult(path, timings, aligned is None)
        except subprocess.TimeoutExpired as exc:
            self.cancel()
            path.unlink(missing_ok=True)
            raise BackendUnavailableError("Piper synthesis timed out") from exc
        except OSError as exc:
            path.unlink(missing_ok=True)
            raise BackendUnavailableError(f"Piper synthesis failed: {exc}") from exc

    def cancel(self) -> None:
        self._cancelled.set()
        with self._lock:
            if self._process and self._process.poll() is None:
                self._process.terminate()
            self._process = None
