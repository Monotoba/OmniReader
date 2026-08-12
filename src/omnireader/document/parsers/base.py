from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from pathlib import Path

from ..model import Block, BlockKind, NormalizedDocument
from ..segmenter import segment_text


class DocumentParseError(RuntimeError):
    pass


def document_id(path: Path) -> str:
    """Stable-enough v1 identity that survives file moves."""
    digest = hashlib.sha256()
    try:
        size = path.stat().st_size
        with path.open("rb") as source:
            digest.update(source.read(256 * 1024))
        digest.update(str(size).encode())
    except OSError:
        digest.update(str(path.resolve()).encode())
    return digest.hexdigest()


def make_block(
    block_id: str,
    text: str,
    kind: BlockKind = "paragraph",
    *,
    source_ref: object = None,
    metadata: dict[str, object] | None = None,
) -> Block:
    normalized = text.replace("\r\n", "\n").strip()
    return Block(
        block_id,
        kind,
        segment_text(normalized),
        normalized,
        source_ref,
        metadata or {},
    )


class DocumentParser(ABC):
    supported_extensions: tuple[str, ...] = ()

    @abstractmethod
    def parse(self, path: Path) -> NormalizedDocument:
        raise NotImplementedError
