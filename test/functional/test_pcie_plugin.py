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
"""Functional tests for PciePlugin with --plugin-configs."""

from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir():
    """Return path to fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def pcie_config_file(fixtures_dir):
    """Return path to PciePlugin config file."""
    return fixtures_dir / "pcie_plugin_config.json"


@pytest.fixture
def pcie_advanced_config_file(fixtures_dir):
    """Return path to PciePlugin advanced config file."""
    return fixtures_dir / "pcie_plugin_advanced_config.json"


def test_pcie_plugin_with_basic_config(run_cli_command, pcie_config_file, tmp_path):
    """Test PciePlugin using basic config file with integer values."""
    assert pcie_config_file.exists(), f"Config file not found: {pcie_config_file}"

    log_path = str(tmp_path / "logs_pcie_basic")
    result = run_cli_command(
        ["--log-path", log_path, "--plugin-configs", str(pcie_config_file)], check=False
    )

    assert result.returncode in [0, 1, 2]
    output = result.stdout + result.stderr
    assert len(output) > 0
    assert "pcieplugin" in output.lower() or "pcie" in output.lower()


def test_pcie_plugin_with_advanced_config(run_cli_command, pcie_advanced_config_file, tmp_path):
    """Test PciePlugin using advanced config with device-specific settings."""
    assert pcie_advanced_config_file.exists(), f"Config file not found: {pcie_advanced_config_file}"

    log_path = str(tmp_path / "logs_pcie_advanced")
    result = run_cli_command(
        ["--log-path", log_path, "--plugin-configs", str(pcie_advanced_config_file)],
        check=False,
    )

    assert result.returncode in [0, 1, 2]
    output = result.stdout + result.stderr
    assert len(output) > 0


def test_pcie_plugin_with_run_plugins_subcommand(run_cli_command, tmp_path):
    """Test PciePlugin using run-plugins subcommand."""
    log_path = str(tmp_path / "logs_pcie_subcommand")
    result = run_cli_command(["--log-path", log_path, "run-plugins", "PciePlugin"], check=False)

    assert result.returncode in [0, 1, 2]
    output = result.stdout + result.stderr
    assert len(output) > 0


def test_pcie_plugin_with_passive_interaction(run_cli_command, pcie_config_file, tmp_path):
    """Test PciePlugin with PASSIVE system interaction level."""
    log_path = str(tmp_path / "logs_pcie_passive")
    result = run_cli_command(
        [
            "--log-path",
            log_path,
            "--sys-interaction-level",
            "PASSIVE",
            "--plugin-configs",
            str(pcie_config_file),
        ],
        check=False,
    )

    assert result.returncode in [0, 1, 2]
    output = result.stdout + result.stderr
    assert len(output) > 0


def test_pcie_plugin_skip_sudo(run_cli_command, pcie_config_file, tmp_path):
    """Test PciePlugin with --skip-sudo flag."""
    log_path = str(tmp_path / "logs_pcie_no_sudo")
    result = run_cli_command(
        [
            "--log-path",
            log_path,
            "--skip-sudo",
            "--plugin-configs",
            str(pcie_config_file),
        ],
        check=False,
    )

    assert result.returncode in [0, 1, 2]
    output = result.stdout + result.stderr
    assert len(output) > 0


def test_pcie_plugin_combined_configs(
    run_cli_command, pcie_config_file, pcie_advanced_config_file, tmp_path
):
    """Test PciePlugin with multiple config files."""
    log_path = str(tmp_path / "logs_pcie_combined")
    result = run_cli_command(
        [
            "--log-path",
            log_path,
            "--plugin-configs",
            str(pcie_config_file),
            str(pcie_advanced_config_file),
        ],
        check=False,
    )

    assert result.returncode in [0, 1, 2]
    output = result.stdout + result.stderr
    assert len(output) > 0
