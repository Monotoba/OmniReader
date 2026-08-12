from __future__ import annotations

from pathlib import Path

from ..model import Block, NormalizedDocument
from .base import DocumentParseError, DocumentParser, document_id
from .html import parse_html_content


class EpubParser(DocumentParser):
    supported_extensions = (".epub",)

    def parse(self, path: Path) -> NormalizedDocument:
        try:
            import ebooklib
            from ebooklib import epub
        except ImportError as exc:
            raise DocumentParseError("EPUB support requires ebooklib") from exc
        try:
            book = epub.read_epub(str(path), options={"ignore_ncx": True})
        except Exception as exc:
            raise DocumentParseError(f"Could not read EPUB file: {exc}") from exc
        blocks: list[Block] = []
        chapters = []
        for chapter_index, item in enumerate(
            book.get_items_of_type(ebooklib.ITEM_DOCUMENT)
        ):
            chapter_blocks = parse_html_content(
                item.get_content().decode("utf-8", "replace"), f"ch-{chapter_index}"
            )
            if chapter_blocks:
                chapters.append(
                    {
                        "id": item.id,
                        "start_block": len(blocks),
                        "title": item.get_name(),
                    }
                )
                blocks.extend(chapter_blocks)
        title_values = book.get_metadata("DC", "title")
        title = title_values[0][0] if title_values else path.stem
        return NormalizedDocument(
            document_id(path),
            title,
            tuple(blocks),
            {"path": str(path), "chapters": chapters},
        )
