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
"""Functional tests for FabricsPlugin with --plugin-configs."""

from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir():
    """Return path to fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def fabrics_config_file(fixtures_dir):
    """Return path to FabricsPlugin config file."""
    return fixtures_dir / "fabrics_plugin_config.json"


def test_fabrics_plugin_with_basic_config(run_cli_command, fabrics_config_file, tmp_path):
    """Test FabricsPlugin using basic config file."""
    assert fabrics_config_file.exists(), f"Config file not found: {fabrics_config_file}"

    log_path = str(tmp_path / "logs_fabrics_basic")
    result = run_cli_command(
        ["--log-path", log_path, "--plugin-configs", str(fabrics_config_file)], check=False
    )

    assert result.returncode in [0, 1, 2]
    output = result.stdout + result.stderr
    assert len(output) > 0
    assert "fabricsplugin" in output.lower() or "fabrics" in output.lower()


def test_fabrics_plugin_with_run_plugins_subcommand(run_cli_command, tmp_path):
    """Test FabricsPlugin using run-plugins subcommand."""
    log_path = str(tmp_path / "logs_fabrics_subcommand")
    result = run_cli_command(["--log-path", log_path, "run-plugins", "FabricsPlugin"], check=False)

    assert result.returncode in [0, 1, 2]
    output = result.stdout + result.stderr
    assert len(output) > 0


def test_fabrics_plugin_with_passive_interaction(run_cli_command, fabrics_config_file, tmp_path):
    """Test FabricsPlugin with PASSIVE system interaction level."""
    log_path = str(tmp_path / "logs_fabrics_passive")
    result = run_cli_command(
        [
            "--log-path",
            log_path,
            "--sys-interaction-level",
            "PASSIVE",
            "--plugin-configs",
            str(fabrics_config_file),
        ],
        check=False,
    )

    assert result.returncode in [0, 1, 2]
    output = result.stdout + result.stderr
    assert len(output) > 0


def test_fabrics_plugin_skip_sudo(run_cli_command, fabrics_config_file, tmp_path):
    """Test FabricsPlugin with --skip-sudo flag."""
    log_path = str(tmp_path / "logs_fabrics_no_sudo")
    result = run_cli_command(
        [
            "--log-path",
            log_path,
            "--skip-sudo",
            "--plugin-configs",
            str(fabrics_config_file),
        ],
        check=False,
    )

    assert result.returncode in [0, 1, 2]
    output = result.stdout + result.stderr
    assert len(output) > 0
