# OmniReader

OmniReader is a Linux-first, read-only desktop document reader. It reads common
document formats aloud with Edge TTS or local Piper voices, automatically falls
back when a backend is unavailable, highlights the current sentence or word,
and remembers tabs, bookmarks, filters, voices, and reading positions.

## Install and run

Python 3.10 or newer is required. A virtual environment is recommended.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
omnireader
```

Piper is optional. Put matching `*.onnx` and `*.onnx.json` voice files in
`~/.local/share/omnireader/piper-voices/`, then install `piper-tts` or place a
`piper` executable on `PATH`. Edge TTS requires a network connection. Legacy
`.doc` conversion requires LibreOffice (`soffice`). Every optional integration
is detected at runtime and fails with an actionable message.

The library database and generated audio cache live below the platform data and
cache directories. Override them for testing with `OMNIREADER_DATA_DIR` and
`OMNIREADER_CACHE_DIR`.

## Development

```bash
python -m pytest
ruff check src tests
mypy src/omnireader
```

`scripts/git-local` behaves like `git` from the project root. It also supports
managed workspaces that keep repository metadata in `.git-local`.

The complete product specification is in
[`docs/omnireader-spec.md`](docs/omnireader-spec.md).

## License

MIT
