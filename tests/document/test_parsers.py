from pathlib import Path

import pytest

from omnireader.document.parsers.base import DocumentParseError
from omnireader.document.parsers.html import HtmlParser
from omnireader.document.parsers.markdown import MarkdownParser
from omnireader.document.parsers.registry import default_registry
from omnireader.document.parsers.txt import TextParser


def test_text_parser_builds_paragraphs_and_stable_id(tmp_path: Path) -> None:
    path = tmp_path / "sample.txt"
    path.write_text("First paragraph.\n\nSecond paragraph.", encoding="utf-8")

    first = TextParser().parse(path)
    moved = tmp_path / "renamed.txt"
    path.rename(moved)
    second = TextParser().parse(moved)

    assert first.doc_id == second.doc_id
    assert [block.plain_text for block in first.blocks] == [
        "First paragraph.",
        "Second paragraph.",
    ]


def test_markdown_parser_tags_headings_lists_and_code(tmp_path: Path) -> None:
    pytest.importorskip("markdown_it")
    path = tmp_path / "sample.md"
    path.write_text("# My title\n\n- One\n- Two\n\n```py\npass\n```", encoding="utf-8")

    document = MarkdownParser().parse(path)

    assert document.title == "My title"
    assert [block.kind for block in document.blocks] == [
        "heading",
        "list_item",
        "list_item",
        "code",
    ]


def test_html_parser_tags_filtered_regions(tmp_path: Path) -> None:
    pytest.importorskip("bs4")
    path = tmp_path / "sample.html"
    path.write_text(
        "<title>Page</title><header><p>Top</p></header>"
        "<main><p>Hello</p><p aria-hidden='true'>Secret</p></main>"
        "<footer><p>Bottom</p></footer>",
        encoding="utf-8",
    )

    document = HtmlParser().parse(path)

    assert document.title == "Page"
    assert [block.kind for block in document.blocks] == [
        "header",
        "paragraph",
        "hidden",
        "footer",
    ]


def test_registry_rejects_unknown_extension(tmp_path: Path) -> None:
    path = tmp_path / "sample.unknown"
    path.write_text("content", encoding="utf-8")

    with pytest.raises(DocumentParseError, match="Unsupported"):
        default_registry().parse(path)
