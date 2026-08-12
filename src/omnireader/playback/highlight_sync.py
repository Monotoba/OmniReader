from __future__ import annotations

from dataclasses import dataclass

from ..document.model import NormalizedDocument, TextPosition


@dataclass(frozen=True, slots=True)
class HighlightSpan:
    block_id: str
    sentence_start: int
    sentence_end: int
    word_start: int | None
    word_end: int | None


def resolve_highlight(
    document: NormalizedDocument, position: TextPosition, word_index: int
) -> HighlightSpan | None:
    block = document.block(position.block_id)
    if not block or position.sentence_index >= len(block.sentences):
        return None
    sentence = block.sentences[position.sentence_index]
    if 0 <= word_index < len(sentence.words):
        word = sentence.words[word_index]
        word_start: int | None = word.char_start
        word_end: int | None = word.char_end
    else:
        word_start = None
        word_end = None
    return HighlightSpan(
        block.id,
        sentence.char_start,
        sentence.char_end,
        word_start,
        word_end,
    )
