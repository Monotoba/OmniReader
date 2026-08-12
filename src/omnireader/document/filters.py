from __future__ import annotations

from dataclasses import dataclass

from .model import Block, NormalizedDocument, TextPosition


@dataclass(frozen=True, slots=True)
class FilterSettings:
    skip_headers_footers: bool = True
    skip_hidden: bool = True
    skip_likely_hidden: bool = False
    skip_code: bool = False
    skip_captions: bool = False

    def excludes(self, block: Block) -> bool:
        if self.skip_headers_footers and block.kind in {"header", "footer"}:
            return True
        if (
            self.skip_hidden
            and block.kind == "hidden"
            and not block.metadata.get("heuristic")
        ):
            return True
        if self.skip_likely_hidden and block.metadata.get("heuristic"):
            return True
        if self.skip_code and block.kind == "code":
            return True
        return self.skip_captions and block.kind == "caption"


def read_queue(
    document: NormalizedDocument, filters: FilterSettings
) -> list[TextPosition]:
    return [
        TextPosition(block.id, sentence_index, 0)
        for block in document.blocks
        if not filters.excludes(block)
        for sentence_index, _sentence in enumerate(block.sentences)
    ]
