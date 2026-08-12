#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
# shellcheck source=_activate_venv.sh
source "$SCRIPT_DIR/_activate_venv.sh"

for module in ruff mypy pytest; do
    if ! python -c "import $module" >/dev/null 2>&1; then
        echo "Development dependency '$module' is not installed in $VIRTUAL_ENV." >&2
        echo "Install development dependencies with:" >&2
        echo "  python -m pip install -e '.[dev]'" >&2
        exit 1
    fi
done

python -m ruff check src tests scripts
python -m mypy src/omnireader
python -m pytest "$@"
python -m compileall -q -x '(^|/)\.venv/' src
