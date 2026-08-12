from omnireader.document.filters import FilterSettings, read_queue
from omnireader.document.model import NormalizedDocument
from omnireader.document.parsers.base import make_block


def test_read_queue_excludes_only_enabled_kinds() -> None:
    document = NormalizedDocument(
        "id",
        "Title",
        (
            make_block("p", "Read me."),
            make_block("h", "Page title", "header"),
            make_block("c", "print('hello')", "code"),
            make_block("x", "White text", "hidden", metadata={"heuristic": True}),
        ),
    )

    queue = read_queue(document, FilterSettings(skip_code=True))

    assert [position.block_id for position in queue] == ["p", "x"]
