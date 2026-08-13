# OmniReader

OmniReader is a Linux-first, read-only desktop document reader. It reads common
document formats aloud with Edge TTS or local Piper voices, automatically falls
back when a backend is unavailable, highlights the current sentence or word,
and remembers tabs, bookmarks, filters, voices, and reading positions.

## Install and run

Python 3.10 or newer is required. A virtual environment is recommended.
Linux audio playback requires `ffplay` (normally provided by the `ffmpeg`
package) or `mpv`. On Ubuntu/Debian:

```bash
sudo apt install ffmpeg
```

Run these commands from the repository root—the directory containing
`pyproject.toml`—not from `src/omnireader`:

```bash
cd /path/to/OmniReader
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
omnireader
```

Once installed, `python -m omnireader` is equivalent to `omnireader`. For a
source-tree launch without installation, use either of these from the
repository root:

```bash
PYTHONPATH=src python -m omnireader
python src/omnireader/main.py
```

The convenience scripts always locate the repository root and activate its
`.venv` before running. They fail with setup instructions if the environment or
development tools are missing:

```bash
./scripts/run.sh [document ...]
./scripts/test.sh
```

Set `OMNIREADER_VENV=/path/to/venv` to use a different virtual environment.
Activation applies to the script process and the application/test process it
starts; a child script cannot alter the calling shell's environment.

On Linux, synthesized audio plays in an `ffplay`/`mpv` child process. This
isolates OmniReader from native multimedia crashes and supports both PulseAudio
and PipeWire's PulseAudio compatibility service. Audio service failures appear
as playback errors instead of terminating the application.

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

## Automation

GitHub Actions runs linting, type checks, tests on Python 3.10/3.12/3.13, and
distribution validation for every push and pull request. Dependabot checks
Python and Actions dependencies monthly.

Pushing a tag matching the package version creates a GitHub Release containing
the verified wheel and source distribution:

```bash
git tag v0.1.0
git push origin v0.1.0
```

The release workflow rejects a tag that does not match `[project].version`.

The complete product specification is in
[`docs/omnireader-spec.md`](docs/omnireader-spec.md).

## License

MIT
