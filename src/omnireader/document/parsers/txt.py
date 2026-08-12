from __future__ import annotations

import re
from pathlib import Path

from ..model import NormalizedDocument
from .base import DocumentParser, document_id, make_block


class TextParser(DocumentParser):
    supported_extensions = (".txt",)

    def parse(self, path: Path) -> NormalizedDocument:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        paragraphs = [value for value in re.split(r"\n\s*\n", text) if value.strip()]
        blocks = tuple(
            make_block(f"p-{index}", value) for index, value in enumerate(paragraphs)
        )
        return NormalizedDocument(
            document_id(path), path.stem, blocks, {"path": str(path)}
        )
