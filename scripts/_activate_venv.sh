#!/usr/bin/env bash

# This file is sourced by the public scripts. Do not execute it directly.
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
PROJECT_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
VENV_DIR=${OMNIREADER_VENV:-"$PROJECT_ROOT/.venv"}

if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
    echo "OmniReader virtual environment not found at: $VENV_DIR" >&2
    echo "Create it from the repository root with:" >&2
    echo "  python3 -m venv .venv" >&2
    echo "  . .venv/bin/activate" >&2
    echo "  python -m pip install -e '.[dev]'" >&2
    exit 1
fi

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

if [[ "${VIRTUAL_ENV:-}" != "$VENV_DIR" ]]; then
    echo "Failed to activate OmniReader virtual environment: $VENV_DIR" >&2
    exit 1
fi

cd "$PROJECT_ROOT"

