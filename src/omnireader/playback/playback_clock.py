from __future__ import annotations

from bisect import bisect_right

from ..tts.base import WordTiming


class PlaybackClock:
    def __init__(self, timings: tuple[WordTiming, ...] = ()) -> None:
        self.set_timings(timings)

    def set_timings(self, timings: tuple[WordTiming, ...]) -> None:
        self.timings = timings
        self._starts = tuple(item.start_ms for item in timings)

    def word_at(self, position_ms: int) -> int | None:
        index = bisect_right(self._starts, position_ms) - 1
        if index < 0 or index >= len(self.timings):
            return None
        timing = self.timings[index]
        return timing.word_index if position_ms <= timing.end_ms else None
