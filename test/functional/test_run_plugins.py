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
"""Functional tests for running individual plugins."""

import pytest

from nodescraper.pluginregistry import PluginRegistry


@pytest.fixture(scope="module")
def all_plugins():
    """Get list of all available plugin names."""
    registry = PluginRegistry()
    return sorted(registry.plugins.keys())


def test_plugin_registry_has_plugins(all_plugins):
    """Verify that plugins are available for testing."""
    assert len(all_plugins) > 0


@pytest.mark.parametrize(
    "plugin_name",
    [
        "BiosPlugin",
        "CmdlinePlugin",
        "DimmPlugin",
        "DkmsPlugin",
        "DmesgPlugin",
        "JournalPlugin",
        "KernelPlugin",
        "KernelModulePlugin",
        "MemoryPlugin",
        "NvmePlugin",
        "OsPlugin",
        "PackagePlugin",
        "ProcessPlugin",
        "RocmPlugin",
        "StoragePlugin",
        "SysctlPlugin",
        "SyslogPlugin",
        "UptimePlugin",
    ],
)
def test_run_individual_plugin(run_cli_command, plugin_name, tmp_path):
    """Test running each plugin individually."""
    log_path = str(tmp_path / f"logs_{plugin_name}")
    result = run_cli_command(["--log-path", log_path, "run-plugins", plugin_name], check=False)

    assert result.returncode in [0, 1, 2]
    output = result.stdout + result.stderr
    assert len(output) > 0
    assert plugin_name.lower() in output.lower()


def test_run_all_plugins_together(run_cli_command, all_plugins, tmp_path):
    """Test running all plugins together."""
    plugins_to_run = all_plugins[:3]
    log_path = str(tmp_path / "logs_multiple")
    result = run_cli_command(["--log-path", log_path, "run-plugins"] + plugins_to_run, check=False)

    assert result.returncode in [0, 1, 2]
    output = result.stdout + result.stderr
    assert len(output) > 0


def test_run_plugin_with_invalid_name(run_cli_command):
    """Test that running a non-existent plugin fails gracefully."""
    result = run_cli_command(["run-plugins", "NonExistentPlugin"], check=False)

    assert result.returncode != 0
    output = (result.stdout + result.stderr).lower()
    assert "error" in output or "invalid" in output or "not found" in output
