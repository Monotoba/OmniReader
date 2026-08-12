from omnireader.document.segmenter import segment_text


def test_segmenter_preserves_source_offsets() -> None:
    text = "  Hello, world!  A second sentence?"
    sentences = segment_text(text)

    assert len(sentences) == 2
    assert text[sentences[0].char_start : sentences[0].char_end] == "Hello, world!"
    assert [text[word.char_start : word.char_end] for word in sentences[1].words] == [
        "A",
        "second",
        "sentence?",
    ]


def test_segmenter_handles_text_without_terminal_punctuation() -> None:
    sentences = segment_text("A short line")
    assert len(sentences) == 1
    assert [word.text for word in sentences[0].words] == ["A", "short", "line"]
