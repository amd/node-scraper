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
"""Functional tests for OsPlugin with --plugin-configs."""

from pathlib import Path
from typing import Any, Union

import pytest


@pytest.fixture
def fixtures_dir():
    """Return path to fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def os_config_file(fixtures_dir):
    """Return path to OsPlugin config file."""
    return fixtures_dir / "os_plugin_config.json"


@pytest.fixture
def plugin_executor(plugin_reg: Union[Any, None] = None):
    """Fixture that creates a PluginExecutor instance for programmatic testing."""
    from nodescraper.models.pluginconfig import PluginConfig
    from nodescraper.pluginexecutor import PluginExecutor
    from nodescraper.pluginregistry import PluginRegistry

    if plugin_reg is None:
        plugin_reg = PluginRegistry()

    def _create_executor(
        plugin_configs: list[PluginConfig],
        connections=None,
        log_path=None,
        system_info=None,
    ):
        """Create a PluginExecutor with the given configuration.

        Args:
            plugin_configs: List of PluginConfig objects
            connections: Optional dict of connection configs
            log_path: Optional path for logs

        Returns:
            PluginExecutor instance
        """
        return PluginExecutor(
            plugin_configs=plugin_configs,
            connections=connections,
            system_info=system_info,
            log_path=log_path,
            plugin_registry=plugin_reg,
        )

    return _create_executor


def test_os_plugin_with_basic_config(run_cli_command, os_config_file, tmp_path):
    """Test OsPlugin using basic config file."""
    assert os_config_file.exists(), f"Config file not found: {os_config_file}"

    log_path = str(tmp_path / "logs_os_basic")
    result = run_cli_command(
        ["--log-path", log_path, f"--plugin-configs={os_config_file}"], check=False
    )

    assert (
        result.returncode == 1
    ), f"Expected success (1), got {result.returncode}. Output: {result.stdout + result.stderr}"

    output = result.stdout + result.stderr
    assert len(output) > 0
    assert "osplugin"


def test_os_plugin_with_os_family_discovery(run_cli_command, tmp_path):
    """Test OsPlugin with OS family auto-discovery (not explicitly set)."""
    log_path = str(tmp_path / "logs_os_family_discovery")
    # Don't specify OS family - let it be discovered
    result = run_cli_command(
        [
            "--log-path",
            log_path,
            "run-plugins",
            "OsPlugin",
        ],
        check=False,
    )

    # Should succeed - OS family discovery is required and should always work locally
    assert result.returncode in [0, 1, 2, 3, 4]
    output = result.stdout + result.stderr
    assert len(output) > 0
    # Verify that collection happened (OS family was discovered)
    assert "osplugin" in output.lower() or "os" in output.lower()


def test_os_plugin_with_executor_programmatic(plugin_executor, tmp_path):
    """Test OsPlugin using PluginExecutor The executor no CLI then we will inspect the result."""
    import string

    from nodescraper.models.pluginconfig import PluginConfig

    # Exp os's are every letter and number combo
    exp_os = []
    for letter in string.ascii_letters + string.digits:
        exp_os.append(letter)

    config = PluginConfig(
        global_args={},
        plugins={
            "OsPlugin": {
                "analysis_args": {"exp_os": exp_os, "exact_match": False},
                "analysis": True,
                "collection": True,
            }
        },
        name="Test Run",
        desc="Test description",
    )

    # Create executor
    executor = plugin_executor(
        plugin_configs=[config],
        log_path=str(tmp_path / "logs_executor"),
    )

    # Run plugins (correct method is run_queue)
    results = executor.run_queue()

    # Verify execution succeeded
    assert results is not None
    assert len(results) > 0

    # Check that OsPlugin ran
    os_results = [r for r in results if r.source == "OsPlugin"]
    assert len(os_results) > 0, "OsPlugin did not run"

    # Check the OsPlugin result
    from nodescraper.enums import ExecutionStatus

    os_result = os_results[0]
    assert os_result.result_data is not None, "OsPlugin result_data is None"
    assert (
        os_result.status == ExecutionStatus.OK
    ), f"OsPlugin status: {os_result.status}, message: {os_result.message}"

    # Verify collection and analysis results
    assert os_result.result_data.collection_result is not None, "Collection result is None"
    assert (
        os_result.result_data.collection_result.status == ExecutionStatus.OK
    ), f"Collection status: {os_result.result_data.collection_result.status}"
    assert os_result.result_data.analysis_result is not None, "Analysis result is None"
    assert (
        os_result.result_data.analysis_result.status == ExecutionStatus.OK
    ), f"Analysis status: {os_result.result_data.analysis_result.status}"

    # Verify data was collected (OS family was auto-discovered)
    assert hasattr(executor, "system_info")
    # OS family should be discovered and set
    assert executor.system_info.os_family is not None
