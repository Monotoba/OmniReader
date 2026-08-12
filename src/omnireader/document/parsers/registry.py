from __future__ import annotations

from pathlib import Path

from ..model import NormalizedDocument
from .base import DocumentParseError, DocumentParser
from .docx import DocxParser
from .epub import EpubParser
from .html import HtmlParser
from .legacy_doc import LegacyDocParser
from .markdown import MarkdownParser
from .pdf import PdfParser
from .rtf import RtfParser
from .txt import TextParser


class ParserRegistry:
    def __init__(self) -> None:
        self._parsers: dict[str, DocumentParser] = {}

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return tuple(sorted(self._parsers))

    def register(self, parser: DocumentParser) -> None:
        for extension in parser.supported_extensions:
            self._parsers[extension.casefold()] = parser

    def parser_for(self, path: Path) -> DocumentParser:
        parser = self._parsers.get(path.suffix.casefold())
        if parser:
            return parser
        try:
            import magic

            mime = magic.from_file(str(path), mime=True)
            aliases = {
                "text/plain": ".txt",
                "text/html": ".html",
                "application/pdf": ".pdf",
                "application/rtf": ".rtf",
                "application/epub+zip": ".epub",
            }
            parser = self._parsers.get(aliases.get(mime, ""))
        except (ImportError, OSError):
            parser = None
        if not parser:
            supported = ", ".join(self.supported_extensions)
            raise DocumentParseError(
                f"Unsupported document format. Supported: {supported}"
            )
        return parser

    def parse(self, path: str | Path) -> NormalizedDocument:
        resolved = Path(path).expanduser().resolve()
        if not resolved.is_file():
            raise DocumentParseError(f"Document does not exist: {resolved}")
        return self.parser_for(resolved).parse(resolved)


def default_registry() -> ParserRegistry:
    registry = ParserRegistry()
    for parser in (
        TextParser(),
        MarkdownParser(),
        HtmlParser(),
        DocxParser(),
        LegacyDocParser(),
        PdfParser(),
        EpubParser(),
        RtfParser(),
    ):
        registry.register(parser)
    return registry
