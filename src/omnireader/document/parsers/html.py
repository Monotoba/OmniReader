from __future__ import annotations

import re
from pathlib import Path

from ..model import Block, BlockKind, NormalizedDocument
from .base import DocumentParseError, DocumentParser, document_id, make_block

_BLOCK_TAGS = {
    "p",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "pre",
    "blockquote",
    "figcaption",
    "td",
    "th",
}


def parse_html_content(content: str, prefix: str = "html") -> tuple[Block, ...]:
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise DocumentParseError("HTML support requires beautifulsoup4") from exc
    soup = BeautifulSoup(content, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    blocks: list[Block] = []
    for tag in soup.find_all(_BLOCK_TAGS):
        if tag.find_parent(_BLOCK_TAGS):
            continue
        text = tag.get_text(" ", strip=True)
        if not text:
            continue
        ancestors = [tag, *tag.parents]
        style = " ".join(
            str(node.get("style", "")) for node in ancestors if hasattr(node, "get")
        )
        hidden = any(
            getattr(node, "get", lambda *_: None)("hidden") is not None
            or str(getattr(node, "get", lambda *_: "")("aria-hidden", "")).lower()
            == "true"
            for node in ancestors
        ) or bool(re.search(r"display\s*:\s*none|visibility\s*:\s*hidden", style, re.I))
        parent_names = {getattr(node, "name", None) for node in ancestors}
        if hidden:
            kind: BlockKind = "hidden"
        elif (
            "header" in parent_names or "nav" in parent_names or "aside" in parent_names
        ):
            kind = "header"
        elif "footer" in parent_names:
            kind = "footer"
        elif tag.name.startswith("h"):
            kind = "heading"
        elif tag.name == "li":
            kind = "list_item"
        elif tag.name == "pre":
            kind = "code"
        elif tag.name == "figcaption":
            kind = "caption"
        elif tag.name in {"td", "th"}:
            kind = "table_cell"
        else:
            kind = "paragraph"
        blocks.append(make_block(f"{prefix}-{len(blocks)}", text, kind))
    return tuple(blocks)


class HtmlParser(DocumentParser):
    supported_extensions = (".html", ".htm")

    def parse(self, path: Path) -> NormalizedDocument:
        content = path.read_text(encoding="utf-8-sig", errors="replace")
        blocks = parse_html_content(content)
        title = path.stem
        try:
            from bs4 import BeautifulSoup

            page_title = BeautifulSoup(content, "lxml").title
            if page_title and page_title.string:
                title = page_title.string.strip()
        except ImportError:
            pass
        return NormalizedDocument(document_id(path), title, blocks, {"path": str(path)})
