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
import json
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from nodescraper.connection.redfish import (
    RedfishGetResult,
    RedfishSshProxyConnectionManager,
)
from nodescraper.connection.redfish.ssh_proxy_connection import (
    CurlResponse,
    SshProxyRedfishConnection,
)
from nodescraper.enums import ExecutionStatus, OSFamily, SystemLocation
from nodescraper.models import PluginConfig, SystemInfo
from nodescraper.pluginexecutor import PluginExecutor
from nodescraper.pluginregistry import PluginRegistry
from nodescraper.plugins.ooband.redfish_inventory import (
    AmcRedfishInventoryPlugin,
    RedfishInventoryCollector,
    RedfishInventoryCollectorArgs,
    RedfishInventoryPlugin,
)

ROOT = "/redfish/v1"
CHASSIS = "/redfish/v1/Chassis"
CHASSIS_MEMBER = "/redfish/v1/Chassis/1"
ASSEMBLY = "/redfish/v1/Chassis/1/Assembly"
POWER = "/redfish/v1/Chassis/1/PowerSubsystem"
SYSTEMS = "/redfish/v1/Systems"
SYSTEM = "/redfish/v1/Systems/1"
MEMORY = "/redfish/v1/Systems/1/Memory"
MEMORY_MEMBER = "/redfish/v1/Systems/1/Memory/1"
PROCESSORS = "/redfish/v1/Systems/1/Processors"
PROCESSOR = "/redfish/v1/Systems/1/Processors/1"


def _body(path: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"@odata.id": path}
    payload.update(extra)
    return payload


def _service() -> dict[str, dict]:
    return {
        ROOT: _body(
            ROOT,
            Chassis={"@odata.id": CHASSIS},
            Systems={"@odata.id": SYSTEMS},
            Oem={"Secret": {"@odata.id": "/redfish/v1/Oem/Secret"}},
        ),
        CHASSIS: _body(CHASSIS, Members=[{"@odata.id": CHASSIS_MEMBER}]),
        CHASSIS_MEMBER: _body(
            CHASSIS_MEMBER,
            Assembly={"@odata.id": ASSEMBLY + "#/Assemblies/0"},
            PowerSubsystem={"@odata.id": POWER},
        ),
        POWER: _body(POWER, Id="Power"),
        SYSTEMS: _body(
            SYSTEMS,
            Members=[{"@odata.id": SYSTEM}],
            **{"Members@odata.nextLink": SYSTEMS + "?$skip=1"},
        ),
        SYSTEMS + "?$skip=1": _body(SYSTEMS + "?$skip=1", Members=[{"@odata.id": SYSTEM + "b"}]),
        SYSTEM: _body(
            SYSTEM,
            Memory={"@odata.id": MEMORY},
            Processors={"@odata.id": PROCESSORS},
        ),
        MEMORY: _body(MEMORY, Members=[{"@odata.id": MEMORY_MEMBER}]),
        MEMORY_MEMBER: _body(MEMORY_MEMBER, Id="1"),
        PROCESSORS: _body(PROCESSORS, Members=[{"@odata.id": PROCESSOR}]),
        PROCESSOR: _body(PROCESSOR, Id="CPU1"),
    }


def _run_get(service: dict[str, dict]):
    def run_get(path: str) -> RedfishGetResult:
        body = service.get(path)
        if body is None:
            return RedfishGetResult(path=path, success=False, error="missing", status_code=404)
        return RedfishGetResult(path=path, success=True, data=body, status_code=200)

    return run_get


def test_bmc_profile_reads_chassis_power_and_system(system_info, redfish_conn_mock):
    redfish_conn_mock.api_root = "redfish/v1"
    redfish_conn_mock.run_get.side_effect = _run_get(_service())
    collector = RedfishInventoryCollector(system_info=system_info, connection=redfish_conn_mock)
    result, data = collector.collect_data(args=RedfishInventoryCollectorArgs(profile="bmc"))
    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert data.responses[CHASSIS_MEMBER]["@odata.id"] == CHASSIS_MEMBER
    assert data.responses[POWER]["Id"] == "Power"
    assert data.responses[SYSTEM]["@odata.id"] == SYSTEM
    assert ASSEMBLY not in data.responses
    assert MEMORY not in data.responses
    assert "/redfish/v1/Oem/Secret" not in data.responses


def test_smc_profile_reads_memory_and_processors(system_info, redfish_conn_mock):
    redfish_conn_mock.api_root = "redfish/v1"
    redfish_conn_mock.run_get.side_effect = _run_get(_service())
    collector = RedfishInventoryCollector(system_info=system_info, connection=redfish_conn_mock)
    result, data = collector.collect_data(
        args=RedfishInventoryCollectorArgs(profile="smc", max_pages=1)
    )
    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert data.responses[MEMORY_MEMBER]["Id"] == "1"
    assert data.responses[PROCESSOR]["Id"] == "CPU1"
    assert CHASSIS not in data.responses
    assert SYSTEMS + "?$skip=1" not in data.responses


def test_max_pages_keeps_the_next_collection_page(system_info, redfish_conn_mock):
    redfish_conn_mock.api_root = "redfish/v1"
    redfish_conn_mock.run_get.side_effect = _run_get(_service())
    collector = RedfishInventoryCollector(system_info=system_info, connection=redfish_conn_mock)
    result, data = collector.collect_data(
        args=RedfishInventoryCollectorArgs(profile="smc", max_pages=2)
    )
    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert SYSTEMS + "?$skip=1" in data.responses


def test_missing_service_root_is_an_error(system_info, redfish_conn_mock):
    redfish_conn_mock.api_root = "redfish/v1"
    redfish_conn_mock.run_get.return_value = RedfishGetResult(
        path=ROOT, success=False, error="refused", status_code=None
    )
    collector = RedfishInventoryCollector(system_info=system_info, connection=redfish_conn_mock)
    result, data = collector.collect_data(args=RedfishInventoryCollectorArgs(profile="bmc"))
    assert result.status == ExecutionStatus.ERROR
    assert data is None


def test_plugin_registers_collector():
    assert RedfishInventoryPlugin.COLLECTOR is RedfishInventoryCollector
    assert RedfishInventoryPlugin.DATA_MODEL.__name__ == "RedfishInventoryDataModel"
    assert RedfishInventoryPlugin.ANALYZER is None


def test_amc_inventory_plugin_uses_the_ssh_proxy():
    assert AmcRedfishInventoryPlugin.CONNECTION_TYPE is RedfishSshProxyConnectionManager
    assert AmcRedfishInventoryPlugin.COLLECTOR is RedfishInventoryCollector
    assert AmcRedfishInventoryPlugin.DATA_MODEL is RedfishInventoryPlugin.DATA_MODEL
    assert AmcRedfishInventoryPlugin.COLLECTOR_ARGS is RedfishInventoryCollectorArgs
    assert AmcRedfishInventoryPlugin.ANALYZER is None
    assert "AmcRedfishInventoryPlugin" in PluginRegistry().plugins


BASE = "http://192.0.2.10:80"
PROXY_SERVICE = {
    ROOT: _body(ROOT, Chassis={"@odata.id": CHASSIS}),
    CHASSIS: _body(CHASSIS, Members=[{"@odata.id": CHASSIS_MEMBER}]),
    CHASSIS_MEMBER: _body(CHASSIS_MEMBER, PowerSubsystem={"@odata.id": POWER}),
    POWER: _body(POWER, Id="Power"),
}


def _fake_curl(self: SshProxyRedfishConnection, url: str, extra_flags: str = "") -> CurlResponse:
    cast(MagicMock, self._shell).urls.append(url)
    path = url[len(BASE) :].rstrip("/") or "/"
    body = PROXY_SERVICE.get(path)
    if body is None:
        return CurlResponse(404, b"")
    return CurlResponse(200, json.dumps(body).encode())


def test_inventory_collects_through_ssh_proxy(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    shell = MagicMock(name="bmc-a")
    shell.urls = []

    def make_shell(ssh_params):
        return shell

    with (
        patch(
            "nodescraper.connection.redfish.ssh_proxy_manager.RemoteShell", side_effect=make_shell
        ),
        patch.object(SshProxyRedfishConnection, "_curl", autospec=True, side_effect=_fake_curl),
    ):
        executor = PluginExecutor(
            plugin_configs=[
                PluginConfig(
                    plugins={"RedfishInventoryPlugin": {"collection_args": {"profile": "bmc"}}}
                )
            ],
            connections={
                "RedfishSshProxyConnectionManager": {
                    "host": "192.0.2.10",
                    "ssh": {"hostname": "bmc-a", "username": "root", "password": "x"},
                }
            },
            system_info=SystemInfo(
                name="test", location=SystemLocation.REMOTE, os_family=OSFamily.LINUX
            ),
        )
        results = executor.run_queue()

    assert results[0].status == ExecutionStatus.OK, results[0].message
    assert f"{BASE}{POWER}" in shell.urls


UPDATE = "/redfish/v1/UpdateService"
FIRMWARE = "/redfish/v1/UpdateService/FirmwareInventory"
FIRMWARE_MEMBER = "/redfish/v1/UpdateService/FirmwareInventory/bmc"


def _service_with_firmware() -> dict[str, dict]:
    service = _service()
    service[ROOT]["UpdateService"] = {"@odata.id": UPDATE}
    service[UPDATE] = _body(UPDATE, FirmwareInventory={"@odata.id": FIRMWARE})
    service[FIRMWARE] = _body(FIRMWARE, Members=[{"@odata.id": FIRMWARE_MEMBER}])
    service[FIRMWARE_MEMBER] = _body(FIRMWARE_MEMBER, Version="1.0")
    return service


def test_profiles_read_firmware_inventory_members(system_info, redfish_conn_mock):
    redfish_conn_mock.api_root = "redfish/v1"
    redfish_conn_mock.run_get.side_effect = _run_get(_service_with_firmware())
    collector = RedfishInventoryCollector(system_info=system_info, connection=redfish_conn_mock)
    for profile in ("bmc", "smc"):
        result, data = collector.collect_data(args=RedfishInventoryCollectorArgs(profile=profile))
        assert result.status == ExecutionStatus.OK
        assert data is not None
        assert data.responses[FIRMWARE_MEMBER]["Version"] == "1.0"


def test_disabling_update_service_skips_firmware_inventory(system_info, redfish_conn_mock):
    redfish_conn_mock.api_root = "redfish/v1"
    redfish_conn_mock.run_get.side_effect = _run_get(_service_with_firmware())
    collector = RedfishInventoryCollector(system_info=system_info, connection=redfish_conn_mock)
    result, data = collector.collect_data(
        args=RedfishInventoryCollectorArgs(profile="bmc", enabled={"update_service": False})
    )
    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert UPDATE not in data.responses
    assert FIRMWARE_MEMBER not in data.responses


def test_extra_names_append_to_the_profile_set():
    args = RedfishInventoryCollectorArgs(
        profile="bmc",
        collections=["Sensors", "Chassis"],
        member_links=["EnvironmentMetrics", "Assembly"],
    )
    assert args.selected_collections()[:5] == [
        "Chassis",
        "Managers",
        "TelemetryService",
        "UpdateService",
        "Systems",
    ]
    assert args.selected_collections()[-1] == "Sensors"
    assert args.selected_collections().count("Chassis") == 1
    assert args.selected_links()[-1] == "EnvironmentMetrics"
    assert args.selected_links().count("Assembly") == 1
    assert "Memory" not in args.selected_links()


def test_enabled_false_still_removes_an_appended_known_area():
    args = RedfishInventoryCollectorArgs(
        profile="smc",
        collections=["Systems"],
        enabled={"systems": False},
    )
    assert "Systems" not in args.selected_collections()
    assert "UpdateService" in args.selected_collections()


def test_appended_collection_is_read(system_info, redfish_conn_mock):
    sensors = "/redfish/v1/Sensors"
    sensor = "/redfish/v1/Sensors/1"
    service = _service()
    service[ROOT]["Sensors"] = {"@odata.id": sensors}
    service[sensors] = _body(sensors, Members=[{"@odata.id": sensor}])
    service[sensor] = _body(sensor, Id="1")
    redfish_conn_mock.api_root = "redfish/v1"
    redfish_conn_mock.run_get.side_effect = _run_get(service)
    collector = RedfishInventoryCollector(system_info=system_info, connection=redfish_conn_mock)
    result, data = collector.collect_data(
        args=RedfishInventoryCollectorArgs(profile="bmc", collections=["Sensors"])
    )
    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert data.responses[sensor]["Id"] == "1"
    assert CHASSIS_MEMBER in data.responses
    assert MEMORY not in data.responses


def test_default_args_enable_every_inventory_area():
    args = RedfishInventoryCollectorArgs()
    assert args.selected_collections() == [
        "Chassis",
        "Managers",
        "TelemetryService",
        "UpdateService",
        "Systems",
    ]
    assert "Assembly" in args.selected_links()
    assert "PowerSubsystem" in args.selected_links()
    assert "FruDevices" in args.selected_links()
    assert "Memory" in args.selected_links()
    assert "Processors" in args.selected_links()


def test_enabled_can_disable_power_and_turn_systems_on(system_info, redfish_conn_mock):
    redfish_conn_mock.api_root = "redfish/v1"
    redfish_conn_mock.run_get.side_effect = _run_get(_service())
    collector = RedfishInventoryCollector(system_info=system_info, connection=redfish_conn_mock)
    result, data = collector.collect_data(
        args=RedfishInventoryCollectorArgs(
            profile="bmc",
            enabled={"power": False, "systems": True, "memory": True, "processors": False},
        )
    )
    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert CHASSIS_MEMBER in data.responses
    assert POWER not in data.responses
    assert MEMORY_MEMBER in data.responses
    assert PROCESSOR not in data.responses


def test_unknown_inventory_switch_is_rejected():
    with pytest.raises(ValidationError):
        RedfishInventoryCollectorArgs(enabled={"sensors": False})


MISSING_MEMBER = "/redfish/v1/Chassis/missing"
BROKEN_MEMBER = "/redfish/v1/Chassis/broken"


def _service_with_extra_members() -> dict[str, dict]:
    service = _service()
    service[CHASSIS] = _body(
        CHASSIS,
        Members=[
            {"@odata.id": CHASSIS_MEMBER},
            {"@odata.id": MISSING_MEMBER},
            {"@odata.id": BROKEN_MEMBER},
        ],
    )
    return service


def _run_get_with_broken_member(service: dict[str, dict]):
    base = _run_get(service)

    def run_get(path: str) -> RedfishGetResult:
        if path == BROKEN_MEMBER:
            return RedfishGetResult(path=path, success=False, error="broken", status_code=500)
        return base(path)

    return run_get


def test_direct_connection_warns_when_a_listed_member_is_missing(system_info, redfish_conn_mock):
    redfish_conn_mock.api_root = "redfish/v1"
    redfish_conn_mock.run_get.side_effect = _run_get_with_broken_member(
        _service_with_extra_members()
    )
    collector = RedfishInventoryCollector(system_info=system_info, connection=redfish_conn_mock)
    result, data = collector.collect_data(args=RedfishInventoryCollectorArgs(profile="bmc"))
    descriptions = [event.description for event in result.events]
    assert data is not None
    assert CHASSIS_MEMBER in data.responses
    assert any(MISSING_MEMBER in description for description in descriptions)
    assert any(BROKEN_MEMBER in description for description in descriptions)


def test_ssh_proxy_treats_missing_collection_member_as_empty(system_info):
    connection = SshProxyRedfishConnection(shell=MagicMock(), base_url="http://192.0.2.10:80")
    connection.api_root = "redfish/v1"
    connection.run_get = _run_get_with_broken_member(_service_with_extra_members())
    collector = RedfishInventoryCollector(system_info=system_info, connection=connection)
    result, data = collector.collect_data(args=RedfishInventoryCollectorArgs(profile="bmc"))
    descriptions = [event.description for event in result.events]
    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert CHASSIS_MEMBER in data.responses
    assert MISSING_MEMBER not in data.responses
    assert not any(MISSING_MEMBER in description for description in descriptions)
    assert any(BROKEN_MEMBER in description for description in descriptions)
