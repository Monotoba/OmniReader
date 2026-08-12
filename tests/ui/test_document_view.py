from omnireader.document.filters import FilterSettings
from omnireader.document.model import NormalizedDocument, TextPosition
from omnireader.document.parsers.base import make_block
from omnireader.ui.document_view import DocumentView


def test_document_view_renders_and_highlights(qtbot) -> None:
    document = NormalizedDocument("id", "Title", (make_block("p", "Hello world."),))
    view = DocumentView(document)
    qtbot.addWidget(view)

    view.apply_filters(FilterSettings())
    view.highlight(TextPosition("p"), 1, "#ffff00", "#ff0000", False)

    assert view.toPlainText() == "Hello world."
    assert len(view.extraSelections()) == 2
