#!/bin/bash

# Create venv if not present
if [ ! -d "venv" ]; then
    python3 -m venv venv || { echo "Failed to create venv. Try: sudo apt install python3-venv"; exit 1; }
fi

# Activate venv
source venv/bin/activate

# Install package
python3 -m pip install --editable .[dev] --upgrade

# Install pre-commit hooks if available
if command -v pre-commit &> /dev/null; then
    pre-commit install
fi
