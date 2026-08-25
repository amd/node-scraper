#!/usr/bin/env bash

if ! which uv >/dev/null 2>&1; then
    if ! which curl >/dev/null 2>&1; then
        wget -qO- https://astral.sh/uv/install.sh | sh
    else
        curl -LsSf https://astral.sh/uv/install.sh | sh
    fi
    export PATH="$HOME/.local/bin:$PATH"
fi

# Use system certificate store so uv works behind corporate SSL proxies
export UV_SYSTEM_CERTS=1

# Create venv if not already present or if Python version is below 3.9
if [ ! -d "venv" ] || ! venv/bin/python -c 'import sys; exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
    uv venv venv --python python3 --no-python-downloads
fi

# Activate the desired venv
source venv/bin/activate

uv pip install -e ".[dev]"

# Only install pre-commit hooks if not in CI environment
if [ -z "${CI:-}" ]; then
    pre-commit install
fi
