###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
###############################################################################
"""Functional tests for node-scraper CLI help commands."""

import subprocess
import sys


def test_help_command():
    """Test that node-scraper -h displays help information."""
    result = subprocess.run(
        [sys.executable, "-m", "nodescraper.cli.cli", "-h"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()
    assert "node scraper" in result.stdout.lower()
    assert "-h" in result.stdout or "--help" in result.stdout


def test_help_command_long_form():
    """Test that node-scraper --help displays help information."""
    result = subprocess.run(
        [sys.executable, "-m", "nodescraper.cli.cli", "--help"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()
    assert "node scraper" in result.stdout.lower()


def test_no_arguments():
    """Test that node-scraper with no arguments runs the default config."""
    result = subprocess.run(
        [sys.executable, "-m", "nodescraper.cli.cli"],
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert len(result.stdout) > 0 or len(result.stderr) > 0
    output = (result.stdout + result.stderr).lower()
    assert "plugin" in output or "nodescraper" in output


def test_help_shows_subcommands():
    """Test that help output includes available subcommands."""
    result = subprocess.run(
        [sys.executable, "-m", "nodescraper.cli.cli", "-h"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = result.stdout.lower()
    assert "run-plugins" in output or "commands:" in output or "positional arguments:" in output
