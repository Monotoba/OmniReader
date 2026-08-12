from __future__ import annotations

import re
from collections.abc import Iterator

from .model import Sentence, Word

_WORD_RE = re.compile(r"\S+")
_FALLBACK_SENTENCE_RE = re.compile(r".*?(?:[.!?]+(?=\s|$)|$)", re.DOTALL)


def _syntok_spans(text: str) -> Iterator[tuple[int, int]]:
    try:
        from syntok import segmenter
    except ImportError:
        return
    for paragraph in segmenter.analyze(text):
        for sentence in paragraph:
            tokens = list(sentence)
            if tokens:
                yield tokens[0].offset, tokens[-1].offset + len(tokens[-1].value)


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Return trimmed sentence offsets without changing the source text."""
    spans = list(_syntok_spans(text))
    if not spans:
        spans = [
            (match.start(), match.end())
            for match in _FALLBACK_SENTENCE_RE.finditer(text)
        ]
    result: list[tuple[int, int]] = []
    for start, end in spans:
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if start < end:
            result.append((start, end))
    return result


def segment_text(text: str) -> tuple[Sentence, ...]:
    sentences: list[Sentence] = []
    for start, end in sentence_spans(text):
        words = tuple(
            Word(match.group(), match.start(), match.end())
            for match in _WORD_RE.finditer(text, start, end)
        )
        if words:
            sentences.append(Sentence(words, start, end))
    return tuple(sentences)
