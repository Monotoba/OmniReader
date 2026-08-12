from __future__ import annotations

from collections import Counter
from pathlib import Path

from ..model import Block, BlockKind, NormalizedDocument
from .base import DocumentParseError, DocumentParser, document_id, make_block


class PdfParser(DocumentParser):
    supported_extensions = (".pdf",)

    def parse(self, path: Path) -> NormalizedDocument:
        try:
            import fitz
        except ImportError as exc:
            raise DocumentParseError("PDF support requires PyMuPDF") from exc
        blocks: list[tuple[int, float, float, float, str, int]] = []
        try:
            pdf = fitz.open(path)
            for page_number, page in enumerate(pdf):
                height = page.rect.height or 1
                for item in page.get_text("blocks"):
                    x0, y0, x1, y1, text, block_number, *_rest = item
                    cleaned = " ".join(text.split())
                    if cleaned:
                        blocks.append(
                            (
                                page_number,
                                y0 / height,
                                y1 / height,
                                x0,
                                cleaned,
                                block_number,
                            )
                        )
            metadata = dict(pdf.metadata or {})
            pdf.close()
        except Exception as exc:
            raise DocumentParseError(f"Could not extract PDF text: {exc}") from exc

        edge_counts = Counter(
            (round(y0, 2), text.casefold())
            for _page, y0, y1, _x0, text, _number in blocks
            if y0 < 0.12 or y1 > 0.88
        )
        page_count = max((item[0] for item in blocks), default=-1) + 1
        normalized: list[Block] = []
        for page, y0, y1, x0, text, number in blocks:
            repeated = (
                page_count >= 3 and edge_counts[(round(y0, 2), text.casefold())] >= 2
            )
            if repeated and y0 < 0.5:
                kind: BlockKind = "header"
            elif repeated:
                kind = "footer"
            else:
                kind = "paragraph"
            normalized.append(
                make_block(
                    f"page-{page}-block-{number}",
                    text,
                    kind,
                    source_ref={"page": page, "bbox": (x0, y0, y1)},
                )
            )
        title = metadata.get("title") or path.stem
        return NormalizedDocument(
            document_id(path), title, tuple(normalized), {"path": str(path), **metadata}
        )
