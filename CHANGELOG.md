# Changelog

## Unreleased

- Added `scripts/run.sh` and `scripts/test.sh`, which locate and activate the
  project virtual environment before running.
- Excluded accidentally nested virtual environments from byte-compilation
  checks.
- Fixed PySide6 `QMediaPlayer.positionChanged` connection failures caused by a
  `qlonglong`/Python `int` signal mismatch.
- Replaced in-process Qt Multimedia playback with isolated `ffplay`/`mpv`
  playback on Linux, preventing native crashes when PipeWire is unavailable.
- Serialized look-ahead synthesis, made backend-switch cancellation generation
  aware, and preserved each backend's own voice when switching between Edge
  and Piper to prevent playback-transition crashes.

## 0.1.0 — 2026-08-12

- Added the PySide6 multi-document reader interface and session restoration.
- Added TXT, Markdown, HTML, DOCX, DOC, PDF, EPUB, and RTF ingestion.
- Added Edge TTS and Piper backends with automatic fallback and audio caching.
- Added synchronized word/sentence highlighting, navigation, and click-to-seek.
- Added per-document voices, filters, bookmarks, and reading-position persistence.
- Added settings, optional forced alignment, quality checks, and CI.
- Added multi-version CI, distribution validation, Dependabot, and tag-driven
  GitHub Release automation.
- Fixed direct `src/omnireader/main.py` execution and clarified that editable
  installs must be run from the repository root.
