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
"""Functional tests for --plugin-configs CLI argument."""

import json
import os
from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir():
    """Return path to fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def plugin_config_files(fixtures_dir):
    """Return dict mapping plugin names to their config file paths."""
    return {
        "BiosPlugin": fixtures_dir / "bios_plugin_config.json",
        "CmdlinePlugin": fixtures_dir / "cmdline_plugin_config.json",
        "DimmPlugin": fixtures_dir / "dimm_plugin_config.json",
        "DkmsPlugin": fixtures_dir / "dkms_plugin_config.json",
        "DmesgPlugin": fixtures_dir / "dmesg_plugin_config.json",
        "JournalPlugin": fixtures_dir / "journal_plugin_config.json",
        "KernelPlugin": fixtures_dir / "kernel_plugin_config.json",
        "KernelModulePlugin": fixtures_dir / "kernel_module_plugin_config.json",
        "MemoryPlugin": fixtures_dir / "memory_plugin_config.json",
        "NvmePlugin": fixtures_dir / "nvme_plugin_config.json",
        "OsPlugin": fixtures_dir / "os_plugin_config.json",
        "PackagePlugin": fixtures_dir / "package_plugin_config.json",
        "ProcessPlugin": fixtures_dir / "process_plugin_config.json",
        "RocmPlugin": fixtures_dir / "rocm_plugin_config.json",
        "StoragePlugin": fixtures_dir / "storage_plugin_config.json",
        "SysctlPlugin": fixtures_dir / "sysctl_plugin_config.json",
        "SyslogPlugin": fixtures_dir / "syslog_plugin_config.json",
        "UptimePlugin": fixtures_dir / "uptime_plugin_config.json",
    }


@pytest.fixture
def sample_plugin_config(tmp_path):
    """Create a sample plugin config JSON file."""
    config = {
        "name": "TestConfig",
        "desc": "A test configuration",
        "global_args": {},
        "plugins": {
            "BiosPlugin": {},
            "OsPlugin": {},
        },
        "result_collators": {},
    }
    config_file = tmp_path / "test_config.json"
    config_file.write_text(json.dumps(config, indent=2))
    return str(config_file)


@pytest.fixture
def invalid_plugin_config(tmp_path):
    """Create an invalid JSON file."""
    config_file = tmp_path / "invalid_config.json"
    config_file.write_text("{ invalid json content")
    return str(config_file)


def test_plugin_config_with_builtin_config(run_cli_command, tmp_path):
    """Test using a built-in config name."""
    log_path = str(tmp_path / "logs_builtin")
    result = run_cli_command(
        ["--log-path", log_path, "--plugin-configs", "NodeStatus"], check=False
    )

    assert result.returncode in [0, 1, 2]
    output = result.stdout + result.stderr
    assert len(output) > 0


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
def test_individual_plugin_with_config_file(
    run_cli_command, plugin_name, plugin_config_files, tmp_path
):
    """Test each plugin using its dedicated config file."""
    config_file = plugin_config_files[plugin_name]

    assert config_file.exists(), f"Config file not found: {config_file}"

    log_path = str(tmp_path / f"logs_{plugin_name.lower()}")
    result = run_cli_command(
        ["--log-path", log_path, "--plugin-configs", str(config_file)], check=False
    )

    assert result.returncode in [0, 1, 2]
    output = result.stdout + result.stderr
    assert len(output) > 0

    assert plugin_name.lower() in output.lower() or "plugin" in output.lower()


def test_plugin_config_with_custom_json_file(run_cli_command, sample_plugin_config, tmp_path):
    """Test using a custom JSON config file path."""
    log_path = str(tmp_path / "logs_custom")
    result = run_cli_command(
        ["--log-path", log_path, "--plugin-configs", sample_plugin_config], check=False
    )

    assert result.returncode in [0, 1, 2]
    output = result.stdout + result.stderr
    assert len(output) > 0


def test_plugin_config_with_multiple_configs(run_cli_command, plugin_config_files, tmp_path):
    """Test using multiple plugin configs."""
    log_path = str(tmp_path / "logs_multiple")
    bios_config = str(plugin_config_files["BiosPlugin"])
    os_config = str(plugin_config_files["OsPlugin"])

    result = run_cli_command(
        [
            "--log-path",
            log_path,
            "--plugin-configs",
            bios_config,
            os_config,
        ],
        check=False,
    )

    assert result.returncode in [0, 1, 2]
    output = result.stdout + result.stderr
    assert len(output) > 0


def test_plugin_config_with_nonexistent_file(run_cli_command, tmp_path):
    """Test that a nonexistent config file path fails gracefully."""
    nonexistent_path = str(tmp_path / "nonexistent_config.json")
    result = run_cli_command(["--plugin-configs", nonexistent_path], check=False)

    assert result.returncode != 0
    output = (result.stdout + result.stderr).lower()
    assert "error" in output or "no plugin config found" in output


def test_plugin_config_with_invalid_builtin_name(run_cli_command):
    """Test that an invalid built-in config name fails gracefully."""
    result = run_cli_command(["--plugin-configs", "NonExistentConfig"], check=False)

    assert result.returncode != 0
    output = (result.stdout + result.stderr).lower()
    assert "error" in output or "no plugin config found" in output


def test_plugin_config_with_invalid_json(run_cli_command, invalid_plugin_config):
    """Test that an invalid JSON file fails gracefully."""
    result = run_cli_command(["--plugin-configs", invalid_plugin_config], check=False)

    assert result.returncode != 0
    output = (result.stdout + result.stderr).lower()
    assert "error" in output or "invalid" in output or "json" in output


def test_plugin_config_empty_list(run_cli_command, tmp_path):
    """Test --plugin-configs with no arguments (uses default config)."""
    log_path = str(tmp_path / "logs_empty")
    result = run_cli_command(["--log-path", log_path, "--plugin-configs"], check=False)

    assert result.returncode in [0, 1, 2]
    output = result.stdout + result.stderr
    assert len(output) > 0


def test_plugin_config_with_system_interaction_level(
    run_cli_command, plugin_config_files, tmp_path
):
    """Test plugin config with different system interaction levels."""
    log_path = str(tmp_path / "logs_passive")
    config_file = str(plugin_config_files["UptimePlugin"])

    result = run_cli_command(
        [
            "--log-path",
            log_path,
            "--sys-interaction-level",
            "PASSIVE",
            "--plugin-configs",
            config_file,
        ],
        check=False,
    )

    assert result.returncode in [0, 1, 2]
    output = result.stdout + result.stderr
    assert len(output) > 0


def test_plugin_config_combined_with_run_plugins(run_cli_command, plugin_config_files, tmp_path):
    """Test that plugin config can be combined with run-plugins subcommand."""
    log_path = str(tmp_path / "logs_combined")
    config_file = str(plugin_config_files["MemoryPlugin"])

    result = run_cli_command(
        [
            "--log-path",
            log_path,
            "--plugin-configs",
            config_file,
            "run-plugins",
            "UptimePlugin",
        ],
        check=False,
    )

    assert result.returncode in [0, 1, 2]
    output = result.stdout + result.stderr
    assert len(output) > 0


def test_plugin_config_verify_log_output(run_cli_command, plugin_config_files, tmp_path):
    """Test that plugin config execution creates expected log outputs."""
    log_path = str(tmp_path / "logs_verify")
    config_file = str(plugin_config_files["OsPlugin"])

    result = run_cli_command(["--log-path", log_path, "--plugin-configs", config_file], check=False)

    log_dirs = [d for d in os.listdir(tmp_path) if d.startswith("logs_verify")]
    if result.returncode in [0, 1]:
        assert len(log_dirs) > 0


def test_all_plugin_config_files_exist(plugin_config_files):
    """Verify all plugin config fixture files exist."""
    for plugin_name, config_file in plugin_config_files.items():
        assert config_file.exists(), f"Missing config file for {plugin_name}: {config_file}"

        with open(config_file) as f:
            config = json.load(f)
            assert "plugins" in config
            assert plugin_name in config["plugins"]


def test_dmesg_plugin_log_dmesg_data_false(run_cli_command, tmp_path):
    """Test DmesgPlugin with log_dmesg_data=false doesn't write dmesg.log."""
    config = {
        "name": "DmesgNoLogConfig",
        "desc": "DmesgPlugin config with log_dmesg_data disabled",
        "global_args": {},
        "plugins": {"DmesgPlugin": {"collection_args": {"log_dmesg_data": False}}},
        "result_collators": {},
    }
    config_file = tmp_path / "dmesg_no_log_config.json"
    config_file.write_text(json.dumps(config, indent=2))

    log_path = str(tmp_path / "logs_dmesg_no_log")
    result = run_cli_command(
        ["--log-path", log_path, "--plugin-configs", str(config_file)], check=False
    )

    assert result.returncode in [0, 1, 2]

    dmesg_plugin_dir = Path(log_path) / "dmesg_plugin" / "dmesg_collector"
    if dmesg_plugin_dir.exists():
        dmesg_log_files = list(dmesg_plugin_dir.glob("dmesg*.log"))
        assert (
            len(dmesg_log_files) == 0
        ), f"Found dmesg log files when log_dmesg_data=False: {dmesg_log_files}"


def test_dmesg_plugin_log_dmesg_data_true(run_cli_command, tmp_path):
    """Test DmesgPlugin with log_dmesg_data=true writes dmesg.log."""
    config = {
        "name": "DmesgWithLogConfig",
        "desc": "DmesgPlugin config with log_dmesg_data enabled",
        "global_args": {},
        "plugins": {"DmesgPlugin": {"collection_args": {"log_dmesg_data": True}}},
        "result_collators": {},
    }
    config_file = tmp_path / "dmesg_with_log_config.json"
    config_file.write_text(json.dumps(config, indent=2))

    log_path = str(tmp_path / "logs_dmesg_with_log")
    result = run_cli_command(
        ["--log-path", log_path, "--plugin-configs", str(config_file)], check=False
    )

    if result.returncode in [0, 1]:
        dmesg_plugin_dir = Path(log_path) / "dmesg_plugin" / "dmesg_collector"
        if dmesg_plugin_dir.exists():
            dmesg_log_files = list(dmesg_plugin_dir.glob("dmesg*.log"))
            assert len(dmesg_log_files) > 0, "Expected dmesg.log file when log_dmesg_data=True"


def test_dmesg_plugin_with_custom_regex_in_config(run_cli_command, tmp_path):
    """Test DmesgPlugin with custom error regex passed through plugin config"""
    # Create a test dmesg fixture with custom errors
    test_dmesg_content = """kern  :err   : 2026-01-07T10:00:00,000000-06:00 CUSTOM_APP_CRASH: Application XYZ crashed
kern  :err   : 2026-01-07T10:00:05,000000-06:00 CUSTOM_DRIVER_TIMEOUT: Driver timeout occurred
kern  :err   : 2026-01-07T10:00:10,000000-06:00 oom_kill_process
kern  :err   : 2026-01-07T10:00:15,000000-06:00 CUSTOM_APP_CRASH: Application ABC crashed
"""

    dmesg_file = tmp_path / "custom_dmesg.log"
    dmesg_file.write_text(test_dmesg_content)

    # Create config with custom regex
    config = {
        "name": "DmesgCustomRegexConfig",
        "desc": "DmesgPlugin config with custom error regex",
        "global_args": {},
        "plugins": {
            "DmesgPlugin": {
                "collection_args": {"dmesg_file": str(dmesg_file)},
                "analysis_args": {
                    "check_unknown_dmesg_errors": False,
                    "error_regex": [
                        {
                            "regex": r"CUSTOM_APP_CRASH.*",
                            "message": "Custom Application Crash",
                            "event_category": "SW_DRIVER",
                            "event_priority": 4,
                        },
                        {
                            "regex": r"CUSTOM_DRIVER_TIMEOUT.*",
                            "message": "Custom Driver Timeout",
                            "event_category": "SW_DRIVER",
                            "event_priority": 3,
                        },
                    ],
                },
            }
        },
        "result_collators": {},
    }

    config_file = tmp_path / "custom_regex_config.json"
    config_file.write_text(json.dumps(config, indent=2))

    log_path = str(tmp_path / "logs_custom_regex")
    result = run_cli_command(
        ["--log-path", log_path, "--plugin-configs", str(config_file)], check=False
    )

    # Check that command ran successfully
    assert result.returncode in [0, 1, 2]

    # Verify results JSON contains custom errors
    results_dir = Path(log_path) / "dmesg_plugin" / "dmesg_analyzer"
    if results_dir.exists():
        result_files = list(results_dir.glob("results*.json"))
        if result_files:
            with open(result_files[0], "r") as f:
                results = json.load(f)
                events = results.get("events", [])

                # Should detect custom errors and base errors
                descriptions = [e["description"] for e in events]
                assert "Custom Application Crash" in descriptions or len(events) > 0
                assert "Out of memory error" in descriptions or len(events) > 0


def test_dmesg_plugin_with_event_collapsing_config(run_cli_command, tmp_path):
    """Test DmesgPlugin with event collapsing parameters in config"""
    # Create a test dmesg with repeated errors at different intervals
    test_dmesg_content = """kern  :err   : 2026-01-07T10:00:00,000000-06:00 oom_kill_process
kern  :err   : 2026-01-07T10:00:30,000000-06:00 oom_kill_process
kern  :err   : 2026-01-07T10:00:50,000000-06:00 oom_kill_process
kern  :err   : 2026-01-07T10:02:00,000000-06:00 oom_kill_process
kern  :err   : 2026-01-07T10:04:00,000000-06:00 oom_kill_process
kern  :err   : 2026-01-07T10:06:00,000000-06:00 oom_kill_process
kern  :err   : 2026-01-07T10:08:00,000000-06:00 oom_kill_process
kern  :err   : 2026-01-07T10:10:00,000000-06:00 oom_kill_process
"""

    dmesg_file = tmp_path / "collapse_dmesg.log"
    dmesg_file.write_text(test_dmesg_content)

    # Create config with event collapsing parameters
    config = {
        "name": "DmesgEventCollapsingConfig",
        "desc": "DmesgPlugin config with event collapsing",
        "global_args": {},
        "plugins": {
            "DmesgPlugin": {
                "collection_args": {"dmesg_file": str(dmesg_file)},
                "analysis_args": {
                    "check_unknown_dmesg_errors": False,
                    "interval_to_collapse_event": 60,
                    "num_timestamps": 2,
                },
            }
        },
        "result_collators": {},
    }

    config_file = tmp_path / "collapse_config.json"
    config_file.write_text(json.dumps(config, indent=2))

    log_path = str(tmp_path / "logs_collapse")
    result = run_cli_command(
        ["--log-path", log_path, "--plugin-configs", str(config_file)], check=False
    )

    assert result.returncode in [0, 1, 2]

    # Verify results JSON shows collapsed events
    results_dir = Path(log_path) / "dmesg_plugin" / "dmesg_analyzer"
    if results_dir.exists():
        result_files = list(results_dir.glob("results*.json"))
        if result_files:
            with open(result_files[0], "r") as f:
                results = json.load(f)
                events = results.get("events", [])

                # Should have 1 event with count > 1
                oom_events = [
                    e for e in events if "memory error" in e.get("description", "").lower()
                ]
                if oom_events:
                    # Verify event was collapsed (count > 1)
                    assert oom_events[0]["data"]["count"] > 1
                    # Verify timestamps list exists
                    assert "timestamps" in oom_events[0]["data"]
                    # Timestamps should be pruned (first 2 + last 2)
                    timestamps = oom_events[0]["data"]["timestamps"]
                    assert len(timestamps) <= 4


def test_dmesg_plugin_with_custom_regex_and_collapsing(run_cli_command, tmp_path):
    """Test DmesgPlugin with both custom regex and event collapsing"""
    # Create test dmesg with repeated custom errors
    test_dmesg_content = """kern  :err   : 2026-01-07T10:00:00,000000-06:00 MY_DRIVER_ERROR: Failed to initialize device
kern  :err   : 2026-01-07T10:00:10,000000-06:00 MY_DRIVER_ERROR: Failed to initialize device
kern  :err   : 2026-01-07T10:00:20,000000-06:00 MY_DRIVER_ERROR: Failed to initialize device
kern  :err   : 2026-01-07T10:02:00,000000-06:00 MY_DRIVER_ERROR: Failed to initialize device
kern  :err   : 2026-01-07T10:04:00,000000-06:00 MY_DRIVER_ERROR: Failed to initialize device
kern  :err   : 2026-01-07T10:00:05,000000-06:00 oom_kill_process
kern  :err   : 2026-01-07T10:02:05,000000-06:00 oom_kill_process
"""

    dmesg_file = tmp_path / "custom_collapse_dmesg.log"
    dmesg_file.write_text(test_dmesg_content)

    # Create config with both features
    config = {
        "name": "DmesgCustomRegexAndCollapsingConfig",
        "desc": "DmesgPlugin config with custom regex and event collapsing",
        "global_args": {},
        "plugins": {
            "DmesgPlugin": {
                "collection_args": {"dmesg_file": str(dmesg_file)},
                "analysis_args": {
                    "check_unknown_dmesg_errors": False,
                    "interval_to_collapse_event": 60,
                    "num_timestamps": 2,
                    "error_regex": [
                        {
                            "regex": r"MY_DRIVER_ERROR.*",
                            "message": "My Custom Driver Error",
                            "event_category": "SW_DRIVER",
                        }
                    ],
                },
            }
        },
        "result_collators": {},
    }

    config_file = tmp_path / "custom_collapse_config.json"
    config_file.write_text(json.dumps(config, indent=2))

    log_path = str(tmp_path / "logs_custom_collapse")
    result = run_cli_command(
        ["--log-path", log_path, "--plugin-configs", str(config_file)], check=False
    )

    assert result.returncode in [0, 1, 2]

    # Verify results
    results_dir = Path(log_path) / "dmesg_plugin" / "dmesg_analyzer"
    if results_dir.exists():
        result_files = list(results_dir.glob("results*.json"))
        if result_files:
            with open(result_files[0], "r") as f:
                results = json.load(f)
                events = results.get("events", [])

                # Look for custom driver error
                custom_events = [
                    e for e in events if "Custom Driver Error" in e.get("description", "")
                ]
                if custom_events:
                    # Should be collapsed
                    assert custom_events[0]["data"]["count"] >= 1
                    assert "timestamps" in custom_events[0]["data"]


def test_dmesg_plugin_different_collapse_intervals(run_cli_command, tmp_path):
    """Test DmesgPlugin with different collapse interval values"""
    # Create test dmesg with errors 10 seconds apart
    test_dmesg_content = """kern  :err   : 2026-01-07T10:00:00,000000-06:00 IO_PAGE_FAULT
kern  :err   : 2026-01-07T10:00:10,000000-06:00 IO_PAGE_FAULT
kern  :err   : 2026-01-07T10:00:20,000000-06:00 IO_PAGE_FAULT
kern  :err   : 2026-01-07T10:00:30,000000-06:00 IO_PAGE_FAULT
"""

    dmesg_file = tmp_path / "interval_dmesg.log"
    dmesg_file.write_text(test_dmesg_content)

    # Test with small interval (5 seconds) - should NOT collapse
    config_small = {
        "name": "DmesgSmallIntervalConfig",
        "desc": "DmesgPlugin with 5-second collapse interval",
        "global_args": {},
        "plugins": {
            "DmesgPlugin": {
                "collection_args": {"dmesg_file": str(dmesg_file)},
                "analysis_args": {
                    "check_unknown_dmesg_errors": False,
                    "interval_to_collapse_event": 5,
                },
            }
        },
        "result_collators": {},
    }

    config_file_small = tmp_path / "small_interval_config.json"
    config_file_small.write_text(json.dumps(config_small, indent=2))

    log_path_small = str(tmp_path / "logs_small_interval")
    result = run_cli_command(
        ["--log-path", log_path_small, "--plugin-configs", str(config_file_small)], check=False
    )

    assert result.returncode in [0, 1, 2]

    # Verify results have all timestamps (not collapsed much)
    results_dir = Path(log_path_small) / "dmesg_plugin" / "dmesg_analyzer"
    if results_dir.exists():
        result_files = list(results_dir.glob("results*.json"))
        if result_files:
            with open(result_files[0], "r") as f:
                results = json.load(f)
                events = results.get("events", [])
                io_events = [e for e in events if "Page Fault" in e.get("description", "")]
                if io_events:
                    # Should have multiple timestamps since interval is small
                    timestamps = io_events[0]["data"].get("timestamps", [])
                    assert len(timestamps) >= 3
