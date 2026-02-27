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
"""
Functional tests for reference config generation and usage workflow.

Tests the complete workflow:
1. Generate reference config from system using --gen-reference-config
2. Use the generated config with --plugin-configs
"""
import json
from pathlib import Path

import pytest

from nodescraper.pluginregistry import PluginRegistry


def find_reference_config(log_path):
    """Find reference_config.json in timestamped log directory.

    Args:
        log_path: Base log path where logs are stored

    Returns:
        Path to reference_config.json or None if not found
    """
    log_path = Path(log_path)
    if not log_path.exists():
        return None

    log_dirs = list(log_path.glob("scraper_logs_*"))
    if not log_dirs:
        return None

    most_recent = max(log_dirs, key=lambda p: p.stat().st_mtime)

    reference_config = most_recent / "reference_config.json"
    if reference_config.exists():
        return reference_config

    return None


@pytest.fixture(scope="module")
def all_plugin_names():
    """Get list of all available plugin names."""
    registry = PluginRegistry()
    return sorted(registry.plugins.keys())


def test_gen_reference_config_all_plugins(run_cli_command, tmp_path, all_plugin_names):
    """Test generating reference config with all plugins via run-plugins subcommand.

    Note: When running all plugins, some may fail but as long as at least one succeeds,
    the reference config should be generated.
    """
    log_path = str(tmp_path / "logs_gen_ref_all")

    result = run_cli_command(
        [
            "--log-path",
            log_path,
            "--gen-reference-config",
            "run-plugins",
        ]
        + all_plugin_names,
        check=False,
    )

    assert result.returncode in [0, 1, 2, 120], (
        f"Unexpected return code: {result.returncode}\n"
        f"stdout: {result.stdout[:500]}\nstderr: {result.stderr[:500]}"
    )

    reference_config_path = find_reference_config(log_path)

    if reference_config_path is None:
        pytest.skip(
            "reference_config.json was not created - likely all plugins failed or timed out. "
            "This can happen in test environments."
        )

    assert reference_config_path.exists()

    with open(reference_config_path) as f:
        config = json.load(f)
        assert "plugins" in config
        assert isinstance(config["plugins"], dict)
        assert len(config["plugins"]) > 0


def test_gen_reference_config_subset_plugins(run_cli_command, tmp_path):
    """Test generating reference config with a subset of plugins."""
    log_path = str(tmp_path / "logs_gen_ref_subset")
    plugins = ["BiosPlugin", "OsPlugin", "KernelPlugin"]

    result = run_cli_command(
        ["--log-path", log_path, "--gen-reference-config", "run-plugins"] + plugins,
        check=False,
    )

    assert result.returncode in [0, 1, 2]

    reference_config_path = find_reference_config(log_path)
    assert reference_config_path is not None, "reference_config.json was not created"
    assert reference_config_path.exists()

    with open(reference_config_path) as f:
        config = json.load(f)
        assert "plugins" in config


def test_use_generated_reference_config(run_cli_command, tmp_path):
    """Test using a generated reference config with --plugin-configs."""
    gen_log_path = str(tmp_path / "logs_gen")
    use_log_path = str(tmp_path / "logs_use")

    plugins = ["BiosPlugin", "OsPlugin", "UptimePlugin"]

    gen_result = run_cli_command(
        ["--log-path", gen_log_path, "--gen-reference-config", "run-plugins"] + plugins,
        check=False,
    )

    assert gen_result.returncode in [0, 1, 2]

    reference_config_path = find_reference_config(gen_log_path)
    assert reference_config_path is not None, "reference_config.json was not created"
    assert reference_config_path.exists()

    use_result = run_cli_command(
        ["--log-path", use_log_path, "--plugin-configs", str(reference_config_path)],
        check=False,
    )

    assert use_result.returncode in [0, 1, 2]
    output = use_result.stdout + use_result.stderr
    assert len(output) > 0


def test_full_workflow_all_plugins(run_cli_command, tmp_path, all_plugin_names):
    """
    Test complete workflow: generate reference config from all plugins,
    then use it with --plugin-configs.

    Note: May skip if plugins fail to generate config in test environment.
    """
    gen_log_path = str(tmp_path / "logs_gen_workflow")
    use_log_path = str(tmp_path / "logs_use_workflow")

    gen_result = run_cli_command(
        [
            "--log-path",
            gen_log_path,
            "--gen-reference-config",
            "run-plugins",
        ]
        + all_plugin_names,
        check=False,
    )

    assert gen_result.returncode in [0, 1, 2, 120], (
        f"Generation failed with return code {gen_result.returncode}\n"
        f"stdout: {gen_result.stdout[:500]}\n"
        f"stderr: {gen_result.stderr[:500]}"
    )

    reference_config_path = find_reference_config(gen_log_path)

    if reference_config_path is None:
        pytest.skip(
            "reference_config.json was not generated - plugins may have failed in test environment"
        )

    assert reference_config_path.exists()

    with open(reference_config_path) as f:
        config = json.load(f)
        assert "plugins" in config, "Config missing 'plugins' key"

        for _plugin_name, plugin_config in config["plugins"].items():
            if "analysis_args" in plugin_config:
                assert isinstance(plugin_config["analysis_args"], dict)

    use_result = run_cli_command(
        ["--log-path", use_log_path, "--plugin-configs", str(reference_config_path)],
        check=False,
    )

    assert use_result.returncode in [0, 1, 2], (
        f"Using config failed with return code {use_result.returncode}\n"
        f"stdout: {use_result.stdout}\n"
        f"stderr: {use_result.stderr}"
    )

    output = use_result.stdout + use_result.stderr
    assert len(output) > 0, "No output generated when using reference config"

    use_log_dirs = list(Path(tmp_path).glob("logs_use_workflow*"))
    assert len(use_log_dirs) > 0, "No log directory created when using config"


def test_reference_config_with_analysis_args(run_cli_command, tmp_path):
    """Test that generated reference config includes analysis_args where available."""
    log_path = str(tmp_path / "logs_analysis_args")

    plugins_with_build_from_model = [
        "BiosPlugin",
        "CmdlinePlugin",
        "DeviceEnumerationPlugin",
        "DkmsPlugin",
        "KernelPlugin",
        "KernelModulePlugin",
        "MemoryPlugin",
        "OsPlugin",
        "PackagePlugin",
        "ProcessPlugin",
        "RdmaPlugin",
        "RocmPlugin",
        "SysctlPlugin",
    ]

    result = run_cli_command(
        ["--log-path", log_path, "--gen-reference-config", "run-plugins"]
        + plugins_with_build_from_model,
        check=False,
    )

    assert result.returncode in [0, 1, 2, 120]

    reference_config_path = find_reference_config(log_path)

    if reference_config_path is None:
        pytest.skip(
            "reference_config.json was not created - plugins may have failed in test environment"
        )

    assert reference_config_path.exists()

    with open(reference_config_path) as f:
        config = json.load(f)
        plugins_with_args = [
            name for name, conf in config["plugins"].items() if "analysis_args" in conf
        ]
        assert len(plugins_with_args) > 0, "No plugins have analysis_args in generated config"


def test_reference_config_structure(run_cli_command, tmp_path):
    """Test that generated reference config has correct structure."""
    log_path = str(tmp_path / "logs_structure")

    result = run_cli_command(
        ["--log-path", log_path, "--gen-reference-config", "run-plugins", "OsPlugin"],
        check=False,
    )

    assert result.returncode in [0, 1, 2]

    reference_config_path = find_reference_config(log_path)
    assert reference_config_path is not None, "reference_config.json was not created"
    assert reference_config_path.exists()

    with open(reference_config_path) as f:
        config = json.load(f)

        assert "plugins" in config
        assert isinstance(config["plugins"], dict)

        if "OsPlugin" in config["plugins"]:
            os_config = config["plugins"]["OsPlugin"]
            if "analysis_args" in os_config:
                assert "exp_os" in os_config["analysis_args"]


def test_gen_reference_config_without_run_plugins(run_cli_command, tmp_path):
    """Test generating reference config without specifying plugins (uses default)."""
    log_path = str(tmp_path / "logs_default")

    result = run_cli_command(
        ["--log-path", log_path, "--gen-reference-config"],
        check=False,
    )

    assert result.returncode in [0, 1, 2]

    reference_config_path = find_reference_config(log_path)
    assert reference_config_path is not None, "reference_config.json was not created"
    assert reference_config_path.exists()

    with open(reference_config_path) as f:
        config = json.load(f)
        assert "plugins" in config


def test_reference_config_json_valid(run_cli_command, tmp_path):
    """Test that generated reference config is valid JSON."""
    log_path = str(tmp_path / "logs_valid_json")

    result = run_cli_command(
        [
            "--log-path",
            log_path,
            "--gen-reference-config",
            "run-plugins",
            "BiosPlugin",
            "OsPlugin",
        ],
        check=False,
    )

    assert result.returncode in [0, 1, 2]

    reference_config_path = find_reference_config(log_path)
    assert reference_config_path is not None, "reference_config.json was not created"
    assert reference_config_path.exists()

    with open(reference_config_path) as f:
        config = json.load(f)
        json_str = json.dumps(config, indent=2)
        assert len(json_str) > 0

        reparsed = json.loads(json_str)
        assert reparsed == config
