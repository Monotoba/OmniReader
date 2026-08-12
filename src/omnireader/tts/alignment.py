from __future__ import annotations

import contextlib
import json
import tempfile
import wave
from pathlib import Path

from .base import WordTiming


def audio_duration_ms(path: Path) -> int:
    with contextlib.closing(wave.open(str(path), "rb")) as source:
        return round(source.getnframes() / source.getframerate() * 1000)


def estimated_word_timings(
    words: tuple[str, ...], duration_ms: int
) -> tuple[WordTiming, ...]:
    if not words:
        return ()
    weights = [
        max(1, len(word.strip(".,!?;:\"'()[]"))) + (2 if word[-1:] in ".!?" else 0)
        for word in words
    ]
    total = sum(weights)
    cursor = 0
    timings = []
    for index, weight in enumerate(weights):
        end = (
            duration_ms
            if index == len(words) - 1
            else cursor + round(duration_ms * weight / total)
        )
        timings.append(WordTiming(index, cursor, max(cursor + 1, end)))
        cursor = end
    return tuple(timings)


def forced_word_timings(
    audio_path: Path, words: tuple[str, ...], language: str = "eng"
) -> tuple[WordTiming, ...] | None:
    """Align individual words with aeneas, or return None when unavailable."""
    if not words:
        return ()
    try:
        from aeneas.executetask import ExecuteTask
        from aeneas.task import Task
    except (ImportError, OSError):
        return None
    try:
        with tempfile.TemporaryDirectory(prefix="omnireader-align-") as directory:
            text_path = Path(directory) / "words.txt"
            output_path = Path(directory) / "sync.json"
            text_path.write_text("\n".join(words), encoding="utf-8")
            config = (
                f"task_language={language}|is_text_type=plain|"
                "os_task_file_format=json"
            )
            task = Task(config_string=config)
            task.audio_file_path_absolute = str(audio_path)
            task.text_file_path_absolute = str(text_path)
            task.sync_map_file_path_absolute = str(output_path)
            ExecuteTask(task).execute()
            task.output_sync_map_file()
            data = json.loads(output_path.read_text(encoding="utf-8"))
            fragments = data.get("fragments", [])
            if len(fragments) != len(words):
                return None
            return tuple(
                WordTiming(
                    index,
                    round(float(item["begin"]) * 1000),
                    round(float(item["end"]) * 1000),
                )
                for index, item in enumerate(fragments)
            )
    except Exception:
        return None
