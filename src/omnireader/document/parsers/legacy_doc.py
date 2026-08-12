from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from ..model import NormalizedDocument
from .base import DocumentParseError, DocumentParser, document_id
from .docx import DocxParser


class LegacyDocParser(DocumentParser):
    supported_extensions = (".doc",)

    def parse(self, path: Path) -> NormalizedDocument:
        executable = shutil.which("soffice")
        if not executable:
            raise DocumentParseError(
                "Legacy .doc support requires LibreOffice (soffice)"
            )
        with tempfile.TemporaryDirectory(prefix="omnireader-doc-") as directory:
            result = subprocess.run(
                [
                    executable,
                    "--headless",
                    "--convert-to",
                    "docx",
                    "--outdir",
                    directory,
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            converted = Path(directory) / f"{path.stem}.docx"
            if result.returncode or not converted.exists():
                detail = result.stderr.strip() or result.stdout.strip()
                raise DocumentParseError(f"LibreOffice conversion failed: {detail}")
            document = DocxParser().parse(converted)
            return NormalizedDocument(
                document_id(path),
                document.title,
                document.blocks,
                {**document.metadata, "path": str(path), "converted_from": "doc"},
            )
