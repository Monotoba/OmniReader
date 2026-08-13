from __future__ import annotations

import threading
from dataclasses import dataclass

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal, Slot

from ..document.filters import FilterSettings, read_queue
from ..document.model import NormalizedDocument, TextPosition
from ..tts.backend_manager import BackendManager
from ..tts.base import SynthesisResult, TextChunk
from .audio_player import AudioPlayer
from .playback_clock import PlaybackClock


@dataclass(slots=True)
class PlaybackPreferences:
    backend: str = "edge"
    voices: dict[str, str] | None = None
    rate: float = 1.0
    pitch: float = 0.0
    buffer_depth: int = 2


class _WorkerSignals(QObject):
    ready = Signal(int, object)
    failed = Signal(int, str)
    done = Signal(object)


class _SynthesisWorker(QRunnable):
    def __init__(
        self,
        index: int,
        manager: BackendManager,
        chunk: TextChunk,
        preferences: PlaybackPreferences,
        cancelled: threading.Event,
    ) -> None:
        super().__init__()
        self.setAutoDelete(False)
        self.index = index
        self.manager = manager
        self.chunk = chunk
        self.preferences = preferences
        self.cancelled = cancelled
        self.signals = _WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            if self.cancelled.is_set():
                return
            result = self.manager.synthesize(
                self.chunk,
                self.preferences.backend,
                self.preferences.voices or {},
                self.preferences.rate,
                self.preferences.pitch,
                cancellation=self.cancelled,
            )
            if not self.cancelled.is_set():
                self.signals.ready.emit(self.index, result)
        except Exception as exc:
            if not self.cancelled.is_set():
                self.signals.failed.emit(self.index, str(exc))
        finally:
            self.signals.done.emit(self)


class PlaybackEngine(QObject):
    position_changed = Signal(object)
    highlight_changed = Signal(object, int, bool)
    playing_changed = Signal(bool)
    error = Signal(str)
    finished = Signal()

    def __init__(
        self,
        document: NormalizedDocument,
        manager: BackendManager,
        filters: FilterSettings,
        preferences: PlaybackPreferences,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.document = document
        self.manager = manager
        self.filters = filters
        self.preferences = preferences
        self.audio = AudioPlayer(self)
        self.audio.position_changed.connect(self._tick)
        self.audio.finished.connect(self._advance)
        self.audio.error.connect(self.error)
        self.queue = read_queue(document, filters)
        self.index = 0
        self._generation = 0
        self._buffer: dict[int, SynthesisResult] = {}
        self._pending: set[tuple[int, int]] = set()
        self._workers: set[_SynthesisWorker] = set()
        self._retired_workers: set[_SynthesisWorker] = set()
        self._worker_cleanup_scheduled = False
        self._generation_cancelled = threading.Event()
        self._clock = PlaybackClock()
        self._is_playing = False
        self._loaded_index: int | None = None
        self._pending_filters: FilterSettings | None = None
        # TTSBackend instances contain mutable cancellation/process state and
        # must never synthesize concurrently. Look-ahead remains effective:
        # this lane prepares queued chunks sequentially while audio plays.
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)

    @property
    def position(self) -> TextPosition | None:
        return (
            self.queue[self.index]
            if self.queue and self.index < len(self.queue)
            else None
        )

    def set_filters(self, filters: FilterSettings) -> None:
        if self._is_playing:
            self._pending_filters = filters
            return
        self._apply_filters(filters)

    def _apply_filters(self, filters: FilterSettings) -> None:
        current = self.position
        self.audio.stop()
        self._loaded_index = None
        self.filters = filters
        self.queue = read_queue(self.document, filters)
        if current in self.queue:
            self.index = self.queue.index(current)
        else:
            self.index = min(self.index, max(0, len(self.queue) - 1))
        self._invalidate()

    def set_preferences(self, preferences: PlaybackPreferences) -> None:
        if preferences == self.preferences:
            return
        was_playing = self._is_playing
        if was_playing:
            self.audio.stop()
            self._loaded_index = None
        self.preferences = preferences
        self._invalidate(cancel_active=True)
        if was_playing:
            self.play()

    def play(self) -> None:
        if not self.queue:
            self.error.emit(
                "This document has no readable text with the current filters"
            )
            return
        self._is_playing = True
        self.playing_changed.emit(True)
        if self._loaded_index == self.index:
            self.audio.resume()
        elif self.index in self._buffer:
            self._play_current()
        else:
            self._fill_buffer()

    def pause(self) -> None:
        self.audio.pause()
        self._is_playing = False
        self.playing_changed.emit(False)

    def stop(self) -> None:
        self.audio.stop()
        self._loaded_index = None
        self._is_playing = False
        self.playing_changed.emit(False)
        self._invalidate(cancel_active=True)

    def seek(self, position: TextPosition) -> None:
        candidates = [
            index
            for index, value in enumerate(self.queue)
            if value.block_id == position.block_id
        ]
        exact = [
            index
            for index in candidates
            if self.queue[index].sentence_index == position.sentence_index
        ]
        if exact or candidates:
            was_playing = self._is_playing
            self.audio.stop()
            self._loaded_index = None
            self.index = (exact or candidates)[0]
            self._invalidate(cancel_active=True)
            self.position_changed.emit(self.position)
            if was_playing:
                self.play()

    def next_sentence(self) -> None:
        self._move(1)

    def previous_sentence(self) -> None:
        self._move(-1)

    def next_paragraph(self) -> None:
        current = self.position
        if not current:
            return
        for candidate in self.queue[self.index + 1 :]:
            if candidate.block_id != current.block_id:
                self.seek(candidate)
                return

    def previous_paragraph(self) -> None:
        current = self.position
        if not current:
            return
        previous = None
        for candidate in self.queue[: self.index]:
            if candidate.block_id != current.block_id:
                previous = candidate
        if previous:
            first = next(
                item for item in self.queue if item.block_id == previous.block_id
            )
            self.seek(first)

    def _move(self, delta: int) -> None:
        target = (
            max(0, min(len(self.queue) - 1, self.index + delta)) if self.queue else 0
        )
        if self.queue:
            self.seek(self.queue[target])

    def _chunk(self, index: int) -> TextChunk:
        position = self.queue[index]
        block = self.document.block(position.block_id)
        assert block is not None
        sentence = block.sentences[position.sentence_index]
        text = block.plain_text[sentence.char_start : sentence.char_end]
        return TextChunk(text, position, tuple(word.text for word in sentence.words))

    def _fill_buffer(self) -> None:
        generation = self._generation
        cancellation = self._generation_cancelled
        end = min(
            len(self.queue), self.index + max(1, self.preferences.buffer_depth + 1)
        )
        for index in range(self.index, end):
            pending_key = (generation, index)
            if index in self._buffer or pending_key in self._pending:
                continue
            worker = _SynthesisWorker(
                index,
                self.manager,
                self._chunk(index),
                PlaybackPreferences(
                    self.preferences.backend,
                    dict(self.preferences.voices or {}),
                    self.preferences.rate,
                    self.preferences.pitch,
                    self.preferences.buffer_depth,
                ),
                cancellation,
            )
            worker.signals.ready.connect(
                lambda item_index, result, token=generation: self._ready(
                    token, item_index, result
                )
            )
            worker.signals.failed.connect(
                lambda item_index, message, token=generation: self._failed(
                    token, item_index, message
                )
            )
            worker.signals.done.connect(self._worker_done)
            self._pending.add(pending_key)
            self._workers.add(worker)
            self._pool.start(worker)

    def _ready(self, generation: int, index: int, result: SynthesisResult) -> None:
        self._pending.discard((generation, index))
        if generation != self._generation:
            return
        self._buffer[index] = result
        if self._is_playing and index == self.index:
            self._play_current()

    def _failed(self, generation: int, index: int, message: str) -> None:
        self._pending.discard((generation, index))
        if generation == self._generation:
            self._is_playing = False
            self.playing_changed.emit(False)
            self.error.emit(message)

    def _worker_done(self, worker: _SynthesisWorker) -> None:
        # The queued done signal can reach the GUI thread just before run()
        # returns on the worker thread. Keep ownership until Qt confirms the
        # private pool has no active run frames.
        self._retired_workers.add(worker)
        if not self._worker_cleanup_scheduled:
            self._worker_cleanup_scheduled = True
            QTimer.singleShot(0, self._cleanup_workers)

    def _cleanup_workers(self) -> None:
        if self._pool.activeThreadCount():
            QTimer.singleShot(10, self._cleanup_workers)
            return
        self._workers.difference_update(self._retired_workers)
        self._retired_workers.clear()
        self._worker_cleanup_scheduled = False

    def _play_current(self) -> None:
        result = self._buffer.get(self.index)
        if not result:
            self._fill_buffer()
            return
        self._clock.set_timings(result.word_timings)
        self.position_changed.emit(self.position)
        self._loaded_index = self.index
        self.audio.play(result.audio_path)
        self._fill_buffer()

    def _tick(self, milliseconds: int) -> None:
        position = self.position
        result = self._buffer.get(self.index)
        if not position or not result:
            return
        word = (
            -1
            if result.sentence_only_timing
            else (self._clock.word_at(milliseconds) or 0)
        )
        self.highlight_changed.emit(position, word, result.sentence_only_timing)

    def _advance(self) -> None:
        current_position = self.position
        self._loaded_index = None
        self._buffer.pop(self.index, None)
        if self._pending_filters is not None and current_position is not None:
            filters = self._pending_filters
            self._pending_filters = None
            all_positions = read_queue(self.document, FilterSettings(False, False))
            ranks = {position: rank for rank, position in enumerate(all_positions)}
            current_rank = ranks.get(current_position, -1)
            self.filters = filters
            self.queue = read_queue(self.document, filters)
            next_indexes = [
                index
                for index, position in enumerate(self.queue)
                if ranks.get(position, -1) > current_rank
            ]
            if not next_indexes:
                self._is_playing = False
                self.playing_changed.emit(False)
                self.finished.emit()
                return
            self.index = next_indexes[0]
            self._invalidate()
            self._play_current()
            return
        if self.index + 1 >= len(self.queue):
            self._is_playing = False
            self.playing_changed.emit(False)
            self.finished.emit()
            return
        self.index += 1
        self._play_current()

    def _invalidate(self, *, cancel_active: bool = False) -> None:
        self._generation_cancelled.set()
        if cancel_active:
            self.manager.cancel()
        self._generation += 1
        self._generation_cancelled = threading.Event()
        self._buffer.clear()
        self._pending = {key for key in self._pending if key[0] == self._generation}
        if self._is_playing:
            self._fill_buffer()
