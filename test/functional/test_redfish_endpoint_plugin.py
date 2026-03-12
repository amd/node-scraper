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
    """Return path to functional test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def redfish_plugin_config(fixtures_dir):
    """Path to RedfishEndpointPlugin config (URIs + checks)."""
    return fixtures_dir / "redfish_endpoint_plugin_config.json"


@pytest.fixture
def redfish_connection_config(fixtures_dir):
    """Path to Redfish connection config (RedfishConnectionManager)."""
    return fixtures_dir / "redfish_connection_config.json"


def test_redfish_endpoint_plugin_with_config_and_connection(
    run_cli_command, redfish_plugin_config, redfish_connection_config, tmp_path
):
    assert redfish_plugin_config.exists(), f"Config not found: {redfish_plugin_config}"
    assert redfish_connection_config.exists(), f"Config not found: {redfish_connection_config}"

    log_path = str(tmp_path / "logs_redfish")
    result = run_cli_command(
        [
            "--log-path",
            log_path,
            "--connection-config",
            str(redfish_connection_config),
            "--plugin-configs=" + str(redfish_plugin_config),
            "run-plugins",
            "RedfishEndpointPlugin",
        ],
        check=False,
    )

    output = result.stdout + result.stderr
    assert "RedfishEndpointPlugin" in output or "Redfish" in output


def test_redfish_endpoint_plugin_plugin_config_only(
    run_cli_command, redfish_plugin_config, tmp_path
):
    assert redfish_plugin_config.exists()

    log_path = str(tmp_path / "logs_redfish_noconn")
    result = run_cli_command(
        [
            "--log-path",
            log_path,
            "--plugin-configs=" + str(redfish_plugin_config),
            "run-plugins",
            "RedfishEndpointPlugin",
        ],
        check=False,
    )

    output = result.stdout + result.stderr
    assert "RedfishEndpointPlugin" in output or "Redfish" in output


def test_redfish_endpoint_plugin_default_subcommand(
    run_cli_command, redfish_plugin_config, redfish_connection_config, tmp_path
):
    assert redfish_plugin_config.exists()
    assert redfish_connection_config.exists()

    log_path = str(tmp_path / "logs_redfish_default")
    result = run_cli_command(
        [
            "--log-path",
            log_path,
            "--connection-config",
            str(redfish_connection_config),
            "--plugin-configs=" + str(redfish_plugin_config),
            "RedfishEndpointPlugin",
        ],
        check=False,
    )

    output = result.stdout + result.stderr
    assert "RedfishEndpointPlugin" in output or "Redfish" in output
