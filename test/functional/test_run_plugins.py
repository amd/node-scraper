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

import csv
from pathlib import Path

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
        "NetworkPlugin",
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
    """Test that running a non-existent plugin logs a warning and falls back to default config."""
    result = run_cli_command(["run-plugins", "NonExistentPlugin"], check=False)

    # Invalid plugin is ignored and default config runs instead
    # Exit code depends on whether default config plugins succeed
    output = result.stdout + result.stderr
    # Check that warning was logged for invalid plugin
    assert "Invalid plugin name(s) ignored: NonExistentPlugin" in output
    # Check that default config was used
    assert "running default config" in output.lower() or "NodeStatus" in output
    # Verify it didn't crash
    assert "Data written to csv file" in output


def test_run_comma_separated_plugins_with_invalid(run_cli_command):
    """Test that comma-separated plugins run valid ones and ignore invalid ones."""
    result = run_cli_command(["run-plugins", "AmdSmiPlugin,SomePlugin"], check=False)

    output = result.stdout + result.stderr
    # Check that warning was logged for invalid plugin
    assert "Invalid plugin name(s) ignored: SomePlugin" in output
    # Check that AmdSmiPlugin actually ran
    assert "Running plugin AmdSmiPlugin" in output
    # Verify it didn't crash
    assert "Data written to csv file" in output


def test_run_plugin_with_data_file_no_collection(run_cli_command, tmp_path):
    """Test running plugin with --data argument and --collection False."""
    collect_log_path = str(tmp_path / "collect_logs")
    result = run_cli_command(
        ["--log-path", collect_log_path, "run-plugins", "DmesgPlugin"], check=False
    )

    output = result.stdout + result.stderr
    assert result.returncode in [0, 1, 2]

    dmesg_data_file = None
    collect_path = Path(collect_log_path)

    for log_dir in collect_path.glob("*"):
        dmesg_plugin_dir = log_dir / "dmesg_plugin" / "dmesg_collector"
        if dmesg_plugin_dir.exists():
            for dmesg_file in dmesg_plugin_dir.glob("dmesg*.log"):
                dmesg_data_file = str(dmesg_file)
                break

    if not dmesg_data_file:
        sample_dmesg_dir = tmp_path / "sample_data"
        sample_dmesg_dir.mkdir(parents=True, exist_ok=True)
        dmesg_data_file = str(sample_dmesg_dir / "dmesg.log")

        sample_content = """[    0.000000] Linux version 5.15.0-generic (buildd@lcy02-amd64-001)
[    0.001000] Command line: BOOT_IMAGE=/boot/vmlinuz root=UUID=test ro quiet splash
[    1.234567] pci 0000:00:01.0: BAR 0: failed to assign [mem size 0x01000000]
[    2.345678] WARNING: CPU: 0 PID: 1 at drivers/test/test.c:123 test_function+0x123/0x456
[    3.456789] AMD-Vi: Event logged [IO_PAGE_FAULT device=00:14.0 domain=0x0000]
[    4.567890] normal system message
[    5.678901] ACPI Error: Method parse/execution failed
[   10.123456] System is operational
"""
        with open(dmesg_data_file, "w", encoding="utf-8") as f:
            f.write(sample_content)

    analyze_log_path = str(tmp_path / "analyze_logs")
    result = run_cli_command(
        [
            "--log-path",
            analyze_log_path,
            "run-plugins",
            "DmesgPlugin",
            "--data",
            dmesg_data_file,
            "--collection",
            "False",
        ],
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode in [0, 1, 2], f"Unexpected return code: {result.returncode}"
    assert "Data collection not ran" in output or "collection" in output.lower()
    assert "Data written to csv file" in output, "CSV file should be created"

    if "Plugin tasks not ran" in output:
        pytest.fail(
            "Bug regression: Plugin reported 'tasks not ran' with --data file. "
            "Analysis should load data from --data parameter before checking if data is None."
        )

    analyze_path = Path(analyze_log_path)
    csv_files = list(analyze_path.glob("*/nodescraper.csv"))
    assert len(csv_files) > 0, "CSV results file should exist"

    csv_file = csv_files[0]
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

        dmesg_rows = [row for row in rows if "DmesgPlugin" in row.get("Plugin", "")]
        assert len(dmesg_rows) > 0, "DmesgPlugin should have results in CSV"

        dmesg_row = dmesg_rows[0]
        status = dmesg_row.get("Status", "")
        assert status != "NOT_RAN", (
            f"Bug regression: DmesgPlugin status is NOT_RAN with --data file. "
            f"Analysis should have run on provided data. Status: {status}"
        )
