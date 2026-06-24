#!/usr/bin/env bash

# When sourced, avoid set -e/-u: failures would exit the caller's shell.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    set -euo pipefail
fi

_bail() {
    echo "dev-setup.sh: $*" >&2
}

_stop() {
    if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
        exit 1
    else
        return 1
    fi
}

ensure_uv() {
    if command -v uv >/dev/null 2>&1; then
        return 0
    fi
    if ! command -v curl >/dev/null 2>&1; then
        _bail "uv is not installed and curl is unavailable. Install uv: https://docs.astral.sh/uv/getting-started/installation/"
        return 1
    fi
    echo "uv not found; installing via astral.sh installer..."
    if ! curl -LsSf https://astral.sh/uv/install.sh | sh; then
        _bail "uv installer failed. Install manually: https://docs.astral.sh/uv/getting-started/installation/"
        return 1
    fi
    export PATH="${HOME}/.local/bin:${PATH}"
    if ! command -v uv >/dev/null 2>&1; then
        _bail "uv install finished but uv is not on PATH (expected ~/.local/bin)."
        return 1
    fi
    return 0
}

if [ ! -f "pyproject.toml" ]; then
    _bail "Run this script from the node-scraper repository root (pyproject.toml not found)."
    _stop
fi

if ! ensure_uv; then
    _stop
fi

if [ ! -d "venv" ] || ! venv/bin/python -c 'import sys; exit(0 if sys.version_info[:2] == (3, 9) else 1)' 2>/dev/null; then
    [ -d "venv" ] && rm -rf venv
    if ! uv venv venv --python 3.9; then
        _bail "Failed to create venv with Python 3.9. Run: uv python install 3.9"
        _stop
    fi
fi

# shellcheck disable=SC1091
source venv/bin/activate

if ! uv pip install -e ".[dev]"; then
    _bail 'uv pip install -e ".[dev]" failed.'
    _stop
fi

if [ -z "${CI:-}" ]; then
    pre-commit install
fi

echo "dev-setup.sh: venv ready ($(python --version)) at $(pwd)/venv"
