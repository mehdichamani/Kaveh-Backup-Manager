#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check if uv is available
if command -v uv >/dev/null 2>&1; then
    uv sync --quiet
    exec uv run python backup_manager.py "$@"
else
    # Fallback to standard python venv
    if [ ! -d ".venv" ]; then
        echo "Creating virtual environment..."
        python3 -m venv .venv
        .venv/bin/pip install pyyaml PyQt6 rich pyinstaller
    fi
    exec .venv/bin/python backup_manager.py "$@"
fi
