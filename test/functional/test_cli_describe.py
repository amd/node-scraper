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
"""Functional tests for CLI describe command."""


def test_describe_command_list_plugins(run_cli_command):
    """Test that describe command can list all plugins."""
    result = run_cli_command(["describe", "plugin"])

    assert result.returncode == 0
    assert len(result.stdout) > 0
    output = result.stdout.lower()
    assert "available plugins" in output or "biosplugin" in output or "kernelplugin" in output


def test_describe_command_single_plugin(run_cli_command):
    """Test that describe command can describe a single plugin."""
    result = run_cli_command(["describe", "plugin", "BiosPlugin"])

    assert result.returncode == 0
    assert len(result.stdout) > 0
    output = result.stdout.lower()
    assert "bios" in output


def test_describe_invalid_plugin(run_cli_command):
    """Test that describe command handles invalid plugin gracefully."""
    result = run_cli_command(["describe", "plugin", "NonExistentPlugin"])

    assert result.returncode != 0
    output = (result.stdout + result.stderr).lower()
    assert "error" in output or "not found" in output or "invalid" in output
