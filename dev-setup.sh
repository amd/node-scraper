#!/usr/bin/env bash

# Create venv if not already present
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# Activate the desired venv
source venv/bin/activate

python3 -m pip install --editable .[dev] --upgrade

# Only install pre-commit hooks if not in CI environment
if [ -z "$CI" ]; then
    pre-commit install
fi
