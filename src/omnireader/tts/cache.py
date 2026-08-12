from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from .base import SynthesisResult, TextChunk, WordTiming


class AudioCache:
    def __init__(self, root: Path, max_size_mb: int = 512) -> None:
        self.root = root
        self.max_bytes = max_size_mb * 1024 * 1024
        self.root.mkdir(parents=True, exist_ok=True)

    def key(
        self, backend: str, chunk: TextChunk, voice: str, rate: float, pitch: float
    ) -> str:
        payload = json.dumps(
            [backend, chunk.text, voice, round(rate, 3), round(pitch, 3)],
            ensure_ascii=False,
        ).encode()
        return hashlib.sha256(payload).hexdigest()

    def get(self, key: str) -> SynthesisResult | None:
        metadata = self.root / f"{key}.json"
        if not metadata.exists():
            return None
        try:
            value = json.loads(metadata.read_text(encoding="utf-8"))
            audio_path = self.root / value["audio"]
            if not audio_path.exists():
                return None
            timings = tuple(WordTiming(**timing) for timing in value["timings"])
            metadata.touch()
            audio_path.touch()
            return SynthesisResult(audio_path, timings, value["sentence_only"])
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            return None

    def put(self, key: str, result: SynthesisResult) -> SynthesisResult:
        suffix = result.audio_path.suffix or ".audio"
        target = self.root / f"{key}{suffix}"
        if result.audio_path.resolve() != target.resolve():
            shutil.move(str(result.audio_path), target)
        metadata = {
            "audio": target.name,
            "timings": [
                {
                    "word_index": item.word_index,
                    "start_ms": item.start_ms,
                    "end_ms": item.end_ms,
                }
                for item in result.word_timings
            ],
            "sentence_only": result.sentence_only_timing,
        }
        (self.root / f"{key}.json").write_text(json.dumps(metadata), encoding="utf-8")
        self.prune()
        return SynthesisResult(target, result.word_timings, result.sentence_only_timing)

    def prune(self) -> None:
        files = sorted(
            (path for path in self.root.iterdir() if path.is_file()),
            key=lambda path: path.stat().st_atime,
        )
        total = sum(path.stat().st_size for path in files)
        for path in files:
            if total <= self.max_bytes:
                break
            size = path.stat().st_size
            path.unlink(missing_ok=True)
            total -= size

    def clear(self) -> None:
        for path in self.root.iterdir():
            if path.is_file():
                path.unlink()
