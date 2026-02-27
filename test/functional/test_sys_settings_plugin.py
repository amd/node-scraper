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
"""Functional tests for SysSettingsPlugin with --plugin-configs."""

from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir():
    """Return path to fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sys_settings_config_file(fixtures_dir):
    """Return path to SysSettingsPlugin config file."""
    return fixtures_dir / "sys_settings_plugin_config.json"


@pytest.fixture
def plugin_config_json(fixtures_dir):
    """Return path to fixture plugin_config.json."""
    return fixtures_dir / "plugin_config.json"


def test_sys_settings_plugin_with_config_file(run_cli_command, sys_settings_config_file, tmp_path):
    """Test SysSettingsPlugin using config file with collection_args and analysis_args."""
    assert sys_settings_config_file.exists(), f"Config file not found: {sys_settings_config_file}"

    log_path = str(tmp_path / "logs_sys_settings")
    result = run_cli_command(
        ["--log-path", log_path, "--plugin-configs", str(sys_settings_config_file)], check=False
    )

    assert result.returncode in [0, 1, 2]
    output = result.stdout + result.stderr
    assert len(output) > 0
    assert "SysSettingsPlugin" in output or "syssettings" in output.lower()


def test_sys_settings_plugin_with_run_plugins_subcommand(run_cli_command, tmp_path):
    """Test SysSettingsPlugin via run-plugins subcommand (no config; collector gets no paths)."""
    log_path = str(tmp_path / "logs_sys_settings_subcommand")
    result = run_cli_command(
        ["--log-path", log_path, "run-plugins", "SysSettingsPlugin"], check=False
    )

    assert result.returncode in [0, 1, 2]
    output = result.stdout + result.stderr
    assert len(output) > 0
    # Without config, plugin runs with no paths -> NOT_RAN or similar
    assert "SysSettings" in output or "sys" in output.lower()


def test_sys_settings_plugin_output_contains_plugin_result(
    run_cli_command, sys_settings_config_file, tmp_path
):
    """On Linux, plugin runs and table shows SysSettingsPlugin with a status."""
    assert sys_settings_config_file.exists()

    log_path = str(tmp_path / "logs_sys_settings_result")
    result = run_cli_command(
        ["--log-path", log_path, "--plugin-configs", str(sys_settings_config_file)], check=False
    )

    output = result.stdout + result.stderr
    # Table or status line should mention the plugin
    assert "SysSettingsPlugin" in output


def test_sys_settings_plugin_with_plugin_config_json(run_cli_command, plugin_config_json, tmp_path):
    """Functional test: run node-scraper with project plugin_config.json (paths + directory_paths + checks)."""
    assert plugin_config_json.exists(), f"Config not found: {plugin_config_json}"

    log_path = str(tmp_path / "logs_plugin_config")
    result = run_cli_command(
        ["--log-path", log_path, "--plugin-configs", str(plugin_config_json)], check=False
    )

    assert result.returncode in [0, 1, 2]
    output = result.stdout + result.stderr
    assert len(output) > 0
    assert "SysSettingsPlugin" in output
    # Config exercises paths + directory_paths (/sys/class/net) + pattern check; collector/analyzer run
    assert "Sysfs" in output or "sys" in output.lower()
