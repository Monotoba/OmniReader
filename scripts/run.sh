#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=_activate_venv.sh
source "$SCRIPT_DIR/_activate_venv.sh"

if ! python -c "import omnireader" >/dev/null 2>&1; then
    echo "OmniReader is not installed in $VIRTUAL_ENV." >&2
    echo "Install it with: python -m pip install -e '.[dev]'" >&2
    exit 1
fi

exec python -m omnireader "$@"

