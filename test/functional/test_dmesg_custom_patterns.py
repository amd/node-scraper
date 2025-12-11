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
"""Functional tests for DmesgPlugin custom error patterns feature."""

import json
from pathlib import Path

import pytest


@pytest.fixture
def dmesg_config_with_custom_patterns():
    """Return path to dmesg config with custom error patterns."""
    fixtures_dir = Path(__file__).parent / "fixtures"
    config_path = fixtures_dir / "dmesg_plugin_config.json"

    assert config_path.exists(), f"Config file not found: {config_path}"

    with open(config_path) as f:
        config = json.load(f)
        assert "DmesgPlugin" in config["plugins"]
        assert "custom_error_patterns" in config["plugins"]["DmesgPlugin"]["analysis_args"]
        patterns = config["plugins"]["DmesgPlugin"]["analysis_args"]["custom_error_patterns"]
        assert len(patterns) > 0, "custom_error_patterns should not be empty"

    return str(config_path)


@pytest.fixture
def simple_custom_pattern_config(tmp_path):
    """Create a simple config with one custom error pattern."""
    config = {
        "name": "SimpleDmesgCustomPattern",
        "desc": "Simple test config with custom error pattern",
        "global_args": {},
        "plugins": {
            "DmesgPlugin": {
                "analysis_args": {
                    "check_unknown_dmesg_errors": False,
                    "custom_error_patterns": [
                        {
                            "pattern": "test_custom_driver.*failed",
                            "message": "Test custom driver failure",
                            "category": "TEST_DRIVER",
                            "priority": "ERROR",
                        }
                    ],
                }
            }
        },
        "result_collators": {},
    }

    config_file = tmp_path / "simple_custom_pattern.json"
    config_file.write_text(json.dumps(config, indent=2))
    return str(config_file)


@pytest.fixture
def multiple_priority_config(tmp_path):
    """Create a config with custom patterns of different priorities."""
    config = {
        "name": "MultiplePriorityPatterns",
        "desc": "Config with custom patterns of different priority levels",
        "global_args": {},
        "plugins": {
            "DmesgPlugin": {
                "analysis_args": {
                    "check_unknown_dmesg_errors": False,
                    "custom_error_patterns": [
                        {
                            "pattern": "critical_issue",
                            "message": "Critical issue detected",
                            "category": "TEST",
                            "priority": "CRITICAL",
                        },
                        {
                            "pattern": "error_issue",
                            "message": "Error issue detected",
                            "category": "TEST",
                            "priority": "ERROR",
                        },
                        {
                            "pattern": "warning_issue",
                            "message": "Warning issue detected",
                            "category": "TEST",
                            "priority": "WARNING",
                        },
                        {
                            "pattern": "info_issue",
                            "message": "Info issue detected",
                            "category": "TEST",
                            "priority": "INFO",
                        },
                    ],
                }
            }
        },
        "result_collators": {},
    }

    config_file = tmp_path / "multiple_priority.json"
    config_file.write_text(json.dumps(config, indent=2))
    return str(config_file)


@pytest.fixture
def combined_patterns_config(tmp_path):
    """Create a config combining custom patterns with unknown error checking."""
    config = {
        "name": "CombinedPatternsConfig",
        "desc": "Config with custom patterns and unknown error checking",
        "global_args": {},
        "plugins": {
            "DmesgPlugin": {
                "analysis_args": {
                    "check_unknown_dmesg_errors": True,
                    "exclude_category": ["OOM"],
                    "custom_error_patterns": [
                        {
                            "pattern": "application.*crash",
                            "message": "Application crash detected",
                            "category": "APPLICATION",
                            "priority": "ERROR",
                        },
                        {
                            "pattern": "memory.*corruption",
                            "message": "Memory corruption detected",
                            "category": "MEMORY",
                            "priority": "CRITICAL",
                        },
                    ],
                }
            }
        },
        "result_collators": {},
    }

    config_file = tmp_path / "combined_patterns.json"
    config_file.write_text(json.dumps(config, indent=2))
    return str(config_file)


def test_dmesg_config_has_custom_patterns(dmesg_config_with_custom_patterns):
    """Verify the dmesg config file includes custom error patterns."""
    with open(dmesg_config_with_custom_patterns) as f:
        config = json.load(f)

    assert "DmesgPlugin" in config["plugins"]
    analysis_args = config["plugins"]["DmesgPlugin"]["analysis_args"]
    assert "custom_error_patterns" in analysis_args

    patterns = analysis_args["custom_error_patterns"]
    assert isinstance(patterns, list)
    assert len(patterns) > 0

    for pattern in patterns:
        assert "pattern" in pattern, "Pattern missing 'pattern' field"
        assert "message" in pattern, "Pattern missing 'message' field"
        assert "category" in pattern, "Pattern missing 'category' field"
        assert "priority" in pattern, "Pattern missing 'priority' field"

        assert pattern["priority"] in ["CRITICAL", "ERROR", "WARNING", "INFO"]


def test_dmesg_plugin_with_custom_patterns_config(
    run_cli_command, dmesg_config_with_custom_patterns, tmp_path
):
    """Test running DmesgPlugin with custom error patterns configuration."""
    log_path = str(tmp_path / "logs_dmesg_custom_patterns")
    result = run_cli_command(
        ["--log-path", log_path, "--plugin-configs", dmesg_config_with_custom_patterns], check=False
    )

    assert result.returncode in [0, 1, 2]

    output = result.stdout + result.stderr
    assert len(output) > 0

    assert "dmesg" in output.lower() or "DmesgPlugin" in output


def test_simple_custom_pattern_config(run_cli_command, simple_custom_pattern_config, tmp_path):
    """Test a simple custom pattern configuration."""
    log_path = str(tmp_path / "logs_simple_custom")
    result = run_cli_command(
        ["--log-path", log_path, "--plugin-configs", simple_custom_pattern_config], check=False
    )

    assert result.returncode in [0, 1, 2]
    output = result.stdout + result.stderr
    assert len(output) > 0


def test_multiple_priority_config(run_cli_command, multiple_priority_config, tmp_path):
    """Test custom patterns with different priority levels."""
    log_path = str(tmp_path / "logs_multiple_priority")
    result = run_cli_command(
        ["--log-path", log_path, "--plugin-configs", multiple_priority_config], check=False
    )

    assert result.returncode in [0, 1, 2]
    output = result.stdout + result.stderr
    assert len(output) > 0


def test_combined_patterns_config(run_cli_command, combined_patterns_config, tmp_path):
    """Test custom patterns combined with unknown error checking."""
    log_path = str(tmp_path / "logs_combined")
    result = run_cli_command(
        ["--log-path", log_path, "--plugin-configs", combined_patterns_config], check=False
    )

    assert result.returncode in [0, 1, 2]
    output = result.stdout + result.stderr
    assert len(output) > 0


def test_custom_patterns_with_invalid_regex(run_cli_command, tmp_path):
    """Test that invalid regex patterns are handled gracefully."""
    config = {
        "name": "InvalidRegexConfig",
        "desc": "Config with invalid regex pattern",
        "global_args": {},
        "plugins": {
            "DmesgPlugin": {
                "analysis_args": {
                    "check_unknown_dmesg_errors": False,
                    "custom_error_patterns": [
                        {
                            "pattern": "[invalid(regex",  # Invalid regex
                            "message": "This should not work",
                            "category": "INVALID",
                            "priority": "ERROR",
                        }
                    ],
                }
            }
        },
        "result_collators": {},
    }

    config_file = tmp_path / "invalid_regex.json"
    config_file.write_text(json.dumps(config, indent=2))

    log_path = str(tmp_path / "logs_invalid_regex")
    result = run_cli_command(
        ["--log-path", log_path, "--plugin-configs", str(config_file)], check=False
    )

    assert result.returncode in [0, 1, 2]
    output = result.stdout + result.stderr
    assert len(output) > 0


def test_custom_patterns_empty_list(run_cli_command, tmp_path):
    """Test that empty custom_error_patterns list works correctly."""
    config = {
        "name": "EmptyCustomPatterns",
        "desc": "Config with empty custom patterns list",
        "global_args": {},
        "plugins": {
            "DmesgPlugin": {
                "analysis_args": {"check_unknown_dmesg_errors": True, "custom_error_patterns": []}
            }
        },
        "result_collators": {},
    }

    config_file = tmp_path / "empty_patterns.json"
    config_file.write_text(json.dumps(config, indent=2))

    log_path = str(tmp_path / "logs_empty_patterns")
    result = run_cli_command(
        ["--log-path", log_path, "--plugin-configs", str(config_file)], check=False
    )

    assert result.returncode in [0, 1, 2]
    output = result.stdout + result.stderr
    assert len(output) > 0


@pytest.mark.parametrize(
    "pattern_spec",
    [
        {
            "pattern": "thermal.*(?:warning|critical)",
            "message": "Thermal issue",
            "category": "THERMAL",
            "priority": "WARNING",
        },
        {
            "pattern": "hardware.*fault",
            "message": "Hardware fault",
            "category": "HARDWARE",
            "priority": "CRITICAL",
        },
        {
            "pattern": "driver.*initialization.*failed",
            "message": "Driver initialization failure",
            "category": "DRIVER",
            "priority": "ERROR",
        },
    ],
)
def test_various_custom_patterns(run_cli_command, pattern_spec, tmp_path):
    """Test various custom pattern specifications."""
    config = {
        "name": "VariousPatternTest",
        "desc": "Test various pattern types",
        "global_args": {},
        "plugins": {
            "DmesgPlugin": {
                "analysis_args": {
                    "check_unknown_dmesg_errors": False,
                    "custom_error_patterns": [pattern_spec],
                }
            }
        },
        "result_collators": {},
    }

    config_file = tmp_path / f"pattern_{pattern_spec['category'].lower()}.json"
    config_file.write_text(json.dumps(config, indent=2))

    log_path = str(tmp_path / f"logs_{pattern_spec['category'].lower()}")
    result = run_cli_command(
        ["--log-path", log_path, "--plugin-configs", str(config_file)], check=False
    )

    assert result.returncode in [0, 1, 2]
    output = result.stdout + result.stderr
    assert len(output) > 0
