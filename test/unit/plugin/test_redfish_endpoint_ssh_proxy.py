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
"""RedfishEndpointPlugin run against a host behind a BMC via RedfishSshProxyConnectionManager.

Only the BMC SSH session and the curl call are faked; the connection manager, executor
connection override, collector and analyzer are the real implementations.
"""
import json
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest

from nodescraper.connection.redfish.ssh_proxy_connection import (
    CurlResponse,
    SshProxyRedfishConnection,
)
from nodescraper.enums import ExecutionStatus, OSFamily, SystemLocation
from nodescraper.models import PluginConfig, SystemInfo
from nodescraper.pluginexecutor import PluginExecutor

BASE = "http://192.0.2.10:80"

CHASSIS = {
    "/redfish/v1": {"@odata.id": "/redfish/v1"},
    "/redfish/v1/Chassis": {"Members@odata.count": 2},
    "/redfish/v1/Chassis/1": {
        "Id": "1",
        "UUID": "123e4567-e89b-12d3-a456-426614174000",
        "SerialNumber": "SN0001",
        "Sensors": {"@odata.id": "/redfish/v1/Chassis/1/Sensors"},
        "Status": {"Health": "OK", "State": "Enabled"},
    },
    "/redfish/v1/Chassis/2": {
        "Id": "2",
        "UUID": "not-a-uuid",
        "SerialNumber": "000000000000",
        "Status": {"Health": "OK", "State": "Enabled"},
    },
}

PLUGIN_ARGS: dict[str, Any] = {
    "connection": "RedfishSshProxyConnectionManager",
    "collection_args": {"uris": ["/redfish/v1/Chassis", "/redfish/v1/Chassis/1"]},
    "analysis_args": {
        "checks": {
            "/redfish/v1/Chassis": {"Members@odata.count": 2},
            "/redfish/v1/Chassis/1": {
                "UUID": {"regex": r"^[0-9a-fA-F-]{36}$"},
                "SerialNumber": {"regex": r"^(?!0+$).+$"},
                "Sensors": {"exists": True},
                "Status/Health": "OK",
            },
        }
    },
}


def _target(hostname: str) -> dict[str, Any]:
    return {
        "host": "192.0.2.10",
        "ssh": {"hostname": hostname, "username": "root", "password": "x"},
    }


def _fake_curl(self: SshProxyRedfishConnection, url: str, extra_flags: str = "") -> CurlResponse:
    cast(MagicMock, self._shell).urls.append(url)
    path = url[len(BASE) :].rstrip("/") or "/"
    body = CHASSIS.get(path)
    if body is None:
        return CurlResponse(404, b"")
    return CurlResponse(200, json.dumps(body).encode())


def _run(connection_args: dict[str, Any], plugin_args: dict[str, Any]):
    shells: dict[str, MagicMock] = {}

    def make_shell(ssh_params):
        shell = MagicMock(name=str(ssh_params.hostname))
        shell.urls = []
        shells[str(ssh_params.hostname)] = shell
        return shell

    with (
        patch(
            "nodescraper.connection.redfish.ssh_proxy_manager.RemoteShell", side_effect=make_shell
        ),
        patch.object(SshProxyRedfishConnection, "_curl", autospec=True, side_effect=_fake_curl),
    ):
        executor = PluginExecutor(
            plugin_configs=[PluginConfig(plugins={"RedfishEndpointPlugin": plugin_args})],
            connections={"RedfishSshProxyConnectionManager": connection_args},
            system_info=SystemInfo(
                name="test", location=SystemLocation.REMOTE, os_family=OSFamily.LINUX
            ),
        )
        results = executor.run_queue()
    return results, shells


@pytest.fixture(autouse=True)
def _no_log_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_single_target_collects_and_checks_through_proxy():
    results, shells = _run(_target("bmc-a"), PLUGIN_ARGS)

    assert len(results) == 1
    assert results[0].status == ExecutionStatus.OK, results[0].message
    assert f"{BASE}/redfish/v1/Chassis/1" in shells["bmc-a"].urls


def test_single_target_reports_failed_checks():
    plugin_args = json.loads(json.dumps(PLUGIN_ARGS))
    plugin_args["collection_args"]["uris"] = ["/redfish/v1/Chassis/2"]
    plugin_args["analysis_args"]["checks"] = {
        "/redfish/v1/Chassis/2": {
            "UUID": {"regex": r"^[0-9a-fA-F-]{36}$"},
            "SerialNumber": {"regex": r"^(?!0+$).+$"},
            "Sensors": {"exists": True},
        }
    }

    results, _ = _run(_target("bmc-a"), plugin_args)

    assert results[0].status == ExecutionStatus.ERROR
    assert "3 check(s) failed" in results[0].message


def test_multi_target_collects_from_each_bmc():
    results, shells = _run({"targets": [_target("bmc-a"), _target("bmc-b")]}, PLUGIN_ARGS)

    assert results[0].status == ExecutionStatus.OK, results[0].message
    for host in ("bmc-a", "bmc-b"):
        assert f"{BASE}/redfish/v1/Chassis/1" in shells[host].urls
