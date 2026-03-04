###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
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

from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir():
    """Return path to fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def nic_plugin_config_full_analyzer_args(fixtures_dir):
    """Return path to NicPlugin config with all analyzer_args populated."""
    return fixtures_dir / "nic_plugin_config_full_analyzer_args.json"


@pytest.fixture
def nic_plugin_config_minimal(fixtures_dir):
    """Return path to minimal NicPlugin config (niccli_plugin_config.json)."""
    return fixtures_dir / "niccli_plugin_config.json"


def test_nic_plugin_with_full_analyzer_args_config(
    run_cli_command, nic_plugin_config_full_analyzer_args, tmp_path
):
    """Test NicPlugin using config with all analyzer_args (performance_profile, getqos, etc.)."""
    assert (
        nic_plugin_config_full_analyzer_args.exists()
    ), f"Config file not found: {nic_plugin_config_full_analyzer_args}"

    log_path = str(tmp_path / "logs_nic_full_args")
    result = run_cli_command(
        [
            "--log-path",
            log_path,
            "--plugin-configs",
            str(nic_plugin_config_full_analyzer_args),
        ],
        check=False,
    )

    assert result.returncode == 0
    output = result.stdout + result.stderr
    assert len(output) > 0
    assert "NicPlugin" in output or "nic" in output.lower()


def test_nic_plugin_with_minimal_config(run_cli_command, nic_plugin_config_minimal, tmp_path):
    """Test NicPlugin using minimal config (default collection_args, no analysis_args)."""
    assert nic_plugin_config_minimal.exists(), f"Config file not found: {nic_plugin_config_minimal}"

    log_path = str(tmp_path / "logs_nic_minimal")
    result = run_cli_command(
        ["--log-path", log_path, "--plugin-configs", str(nic_plugin_config_minimal)],
        check=False,
    )

    assert result.returncode == 0
    output = result.stdout + result.stderr
    assert len(output) > 0
    assert "NicPlugin" in output or "nic" in output.lower()


def test_nic_plugin_with_run_plugins_subcommand(run_cli_command, tmp_path):
    """Test NicPlugin via run-plugins subcommand (no config)."""
    log_path = str(tmp_path / "logs_nic_subcommand")
    result = run_cli_command(["--log-path", log_path, "run-plugins", "NicPlugin"], check=False)

    assert result.returncode == 0
    output = result.stdout + result.stderr
    assert len(output) > 0
    assert "NicPlugin" in output or "nic" in output.lower()


def test_nic_plugin_full_config_validates_analysis_args(
    run_cli_command, nic_plugin_config_full_analyzer_args, tmp_path
):
    """Config with all analyzer_args loads and runs without validation error."""
    assert nic_plugin_config_full_analyzer_args.exists()

    log_path = str(tmp_path / "logs_nic_validate")
    result = run_cli_command(
        [
            "--log-path",
            log_path,
            "--plugin-configs",
            str(nic_plugin_config_full_analyzer_args),
        ],
        check=False,
    )

    assert result.returncode == 0
    output = result.stdout + result.stderr
    assert "NicPlugin" in output
