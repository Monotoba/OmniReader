from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

BlockKind = Literal[
    "paragraph",
    "heading",
    "list_item",
    "header",
    "footer",
    "hidden",
    "code",
    "table_cell",
    "caption",
]


@dataclass(frozen=True, slots=True)
class Word:
    text: str
    char_start: int
    char_end: int


@dataclass(frozen=True, slots=True)
class Sentence:
    words: tuple[Word, ...]
    char_start: int
    char_end: int

    @property
    def text_span(self) -> tuple[int, int]:
        return self.char_start, self.char_end


@dataclass(frozen=True, slots=True)
class Block:
    id: str
    kind: BlockKind
    sentences: tuple[Sentence, ...]
    plain_text: str
    source_ref: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NormalizedDocument:
    doc_id: str
    title: str
    blocks: tuple[Block, ...]
    metadata: dict[str, Any] = field(default_factory=dict)

    def block(self, block_id: str) -> Block | None:
        return next((block for block in self.blocks if block.id == block_id), None)


@dataclass(frozen=True, slots=True)
class TextPosition:
    block_id: str
    sentence_index: int = 0
    word_index: int = 0
