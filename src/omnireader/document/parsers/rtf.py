from __future__ import annotations

import re
from pathlib import Path

from ..model import NormalizedDocument
from .base import DocumentParseError, DocumentParser, document_id, make_block


class RtfParser(DocumentParser):
    supported_extensions = (".rtf",)

    def parse(self, path: Path) -> NormalizedDocument:
        try:
            from striprtf.striprtf import rtf_to_text
        except ImportError as exc:
            raise DocumentParseError("RTF support requires striprtf") from exc
        source = path.read_text(encoding="utf-8", errors="replace")
        try:
            text = rtf_to_text(source)
        except Exception as exc:
            raise DocumentParseError(f"Could not read RTF file: {exc}") from exc
        paragraphs = [value for value in re.split(r"\n\s*\n|\n", text) if value.strip()]
        blocks = tuple(
            make_block(f"p-{index}", value) for index, value in enumerate(paragraphs)
        )
        return NormalizedDocument(
            document_id(path), path.stem, blocks, {"path": str(path)}
        )
