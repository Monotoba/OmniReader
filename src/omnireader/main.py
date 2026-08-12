from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from .config import cache_dir, database_path
from .document.parsers import default_registry
from .persistence.bookmarks_repo import BookmarksRepository
from .persistence.db import Database
from .persistence.documents_repo import DocumentsRepository
from .persistence.settings_repo import SettingsRepository
from .tts.cache import AudioCache
from .ui.main_window import MainWindow


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read documents aloud")
    parser.add_argument("documents", nargs="*", type=Path, help="documents to open")
    parser.add_argument("--debug", action="store_true", help="enable debug logging")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    QCoreApplication.setOrganizationName("OmniReader")
    QCoreApplication.setApplicationName("OmniReader")
    application = QApplication(sys.argv[:1])
    application.setApplicationDisplayName("OmniReader")
    database = Database(database_path())
    settings = SettingsRepository(database)
    cache = AudioCache(cache_dir() / "audio", int(settings.get("storage.cache_max_mb")))
    window = MainWindow(
        default_registry(),
        DocumentsRepository(database),
        BookmarksRepository(database),
        settings,
        cache,
    )
    window.show()
    window.restore_session()
    if args.documents:
        window.open_paths(args.documents)
    result = application.exec()
    database.close()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
