from __future__ import annotations

from pathlib import Path
from typing import cast

from ..model import Block, BlockKind, NormalizedDocument
from .base import DocumentParseError, DocumentParser, document_id, make_block


class MarkdownParser(DocumentParser):
    supported_extensions = (".md", ".markdown")

    def parse(self, path: Path) -> NormalizedDocument:
        try:
            from markdown_it import MarkdownIt
        except ImportError as exc:
            raise DocumentParseError(
                "Markdown support requires markdown-it-py"
            ) from exc
        tokens = MarkdownIt().parse(
            path.read_text(encoding="utf-8-sig", errors="replace")
        )
        blocks: list[Block] = []
        title = path.stem
        context = "paragraph"
        for token in tokens:
            if token.type == "heading_open":
                context = "heading"
            elif token.type in {
                "bullet_list_open",
                "ordered_list_open",
                "list_item_open",
            }:
                context = "list_item"
            elif token.type in {"fence", "code_block"} and token.content.strip():
                blocks.append(make_block(f"b-{len(blocks)}", token.content, "code"))
            elif token.type == "inline" and token.content.strip():
                kind = cast(
                    BlockKind,
                    context if context in {"heading", "list_item"} else "paragraph",
                )
                blocks.append(make_block(f"b-{len(blocks)}", token.content, kind))
                if kind == "heading" and title == path.stem:
                    title = token.content.strip()
            elif token.type == "heading_close":
                context = "paragraph"
        return NormalizedDocument(
            document_id(path), title, tuple(blocks), {"path": str(path)}
        )
