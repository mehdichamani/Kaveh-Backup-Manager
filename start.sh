#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if .venv exists, otherwise create with uv or python
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    if command -v uv >/dev/null 2>&1; then
        uv venv .venv
        uv pip install --python .venv/bin/python -r requirements.txt rich
    else
        python3 -m venv .venv
        .venv/bin/pip install -r requirements.txt rich
    fi
fi

exec .venv/bin/python backup_manager.py "$@"
