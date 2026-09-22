# Contributing to OmniReader

Thanks for helping make document reading more reliable and accessible.

## Report a problem

Search [existing issues](https://github.com/Monotoba/OmniReader/issues) first.
For a new issue, include your Linux distribution, Python version, OmniReader
version or commit, document format, voice backend (Edge or Piper), steps to
reproduce, expected behavior, and actual behavior. Include the exact error
message when possible. For audio problems, mention whether `ffplay` or `mpv`
is installed and whether audio works in other applications.

Do not upload private documents or access tokens. If a file triggers a bug,
try a small, shareable example that reproduces it.

## Make a change

1. Open an issue for substantial changes so the approach can be discussed.
2. Fork and clone the repository, then create a branch from `main`.
3. Set up Python 3.10 or newer in a virtual environment from the repository
   root and run `python -m pip install -e '.[dev]'`.
4. Add or update a focused test when behavior changes. Keep existing formats,
   keyboard behavior, and offline playback working.
5. Run `./scripts/test.sh` and describe the result in your pull request. The
   script runs the project checks; CI also tests Python 3.10, 3.12, and 3.13.
6. Explain the user-facing change, reproduction steps, and any limitations.

The [product specification](docs/omnireader-spec.md) describes the architecture
and planned behavior. Check the implementation before treating a proposed
feature in that document as already available.

## Useful starting points

- Document formats: `src/omnireader/document/parsers/`
- Voice backends: `src/omnireader/tts/`
- Playback: `src/omnireader/playback/`
- Desktop interface: `src/omnireader/ui/`
- Tests: `tests/`

For a small documentation correction, a pull request is welcome without an
issue.
