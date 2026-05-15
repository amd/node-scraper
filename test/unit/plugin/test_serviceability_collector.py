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
from typing import Any, Optional

import pytest
from pydantic import ValidationError

from nodescraper.connection.redfish import (
    RF_MEMBERS,
    RF_MEMBERS_COUNT,
    RedfishGetResult,
)
from nodescraper.enums import ExecutionStatus
from nodescraper.plugins.serviceability import (
    DeviceInfo,
    ServiceabilityCollectorArgs,
    ServiceabilityDataModel,
    ServiceabilityPluginBase,
)
from nodescraper.plugins.serviceability.serviceability_collector import (
    ServiceabilityCollectorBase,
)

EVENT_URI = "/redfish/v1/Systems/1/LogServices/SEL/Entries"


class _StubServiceabilityCollector(ServiceabilityCollectorBase):
    def filter_event_members(
        self,
        members: list[Any],
        args: ServiceabilityCollectorArgs,
    ) -> list[Any]:
        return members

    def is_cper_event(self, event: dict) -> bool:
        return False

    def collect_cper_data(self, rf_events: list[Any]) -> dict[str, Any]:
        return {}

    def parse_assembly_entry(
        self,
        designation: str,
        assembly_member_entry: dict[str, Any],
        args: ServiceabilityCollectorArgs,
    ) -> DeviceInfo:
        return DeviceInfo(name=designation, serial_number=assembly_member_entry.get("SerialNumber"))

    def extract_component_details(
        self,
        firmware_inventory_payload: dict[str, Any],
        args: ServiceabilityCollectorArgs,
    ) -> Optional[str]:
        return firmware_inventory_payload.get("Details")


@pytest.fixture
def stub_serviceability_collector(system_info, redfish_conn_mock):
    redfish_conn_mock.base_url = "https://bmc.example/redfish/v1"
    return _StubServiceabilityCollector(
        system_info=system_info,
        connection=redfish_conn_mock,
        log_path="/tmp/serviceability.log",
    )


def test_serviceability_collector_args_requires_event_log_uri():
    with pytest.raises(ValidationError):
        ServiceabilityCollectorArgs()


def test_serviceability_collector_args_uri_alias_prefers_uri_over_rf_event_log_uri():
    args = ServiceabilityCollectorArgs(uri=" /events ", rf_event_log_uri="/other")
    assert args.resolved_event_log_uri() == "/events"


def test_serviceability_collector_args_assembly_requires_both_template_and_devices():
    with pytest.raises(ValidationError):
        ServiceabilityCollectorArgs(
            rf_event_log_uri=EVENT_URI,
            rf_assembly_uri_template="/redfish/v1/Chassis/{device}/Assembly",
        )
    with pytest.raises(ValidationError):
        ServiceabilityCollectorArgs(
            rf_event_log_uri=EVENT_URI,
            rf_chassis_devices=["C1"],
        )


def test_serviceability_collector_args_assembly_template_must_include_device_placeholder():
    with pytest.raises(ValidationError):
        ServiceabilityCollectorArgs(
            rf_event_log_uri=EVENT_URI,
            rf_assembly_uri_template="/redfish/v1/Chassis/C1/Assembly",
            rf_chassis_devices=["C1"],
        )


def test_serviceability_collector_args_assembly_optional_when_omitted():
    args = ServiceabilityCollectorArgs(rf_event_log_uri=EVENT_URI)
    assert args.rf_assembly_uri_template is None
    assert args.rf_chassis_devices is None


def test_serviceability_plugin_base_wiring():
    assert ServiceabilityPluginBase.DATA_MODEL is ServiceabilityDataModel
    assert ServiceabilityPluginBase.COLLECTOR is ServiceabilityCollectorBase
    assert ServiceabilityPluginBase.COLLECTOR_ARGS is ServiceabilityCollectorArgs
    assert ServiceabilityPluginBase.ANALYZER is None


def test_stub_collector_no_args(stub_serviceability_collector):
    result, data = stub_serviceability_collector.collect_data()
    assert result.status == ExecutionStatus.NOT_RAN
    assert "required" in result.message.lower()
    assert data is None


def test_stub_collector_event_log_get_fails(stub_serviceability_collector, redfish_conn_mock):
    redfish_conn_mock.run_get_paged.return_value = RedfishGetResult(
        path=EVENT_URI,
        success=False,
        error="timeout",
        status_code=None,
    )
    args = ServiceabilityCollectorArgs(rf_event_log_uri=EVENT_URI)
    result, data = stub_serviceability_collector.collect_data(args=args)
    assert result.status == ExecutionStatus.ERROR
    assert EVENT_URI in result.message
    assert data is None


def test_stub_collector_success_minimal(stub_serviceability_collector, redfish_conn_mock):
    members = [{"Id": "1"}]
    redfish_conn_mock.run_get_paged.return_value = RedfishGetResult(
        path=EVENT_URI,
        success=True,
        data={RF_MEMBERS: members},
        status_code=200,
    )
    args = ServiceabilityCollectorArgs(rf_event_log_uri=EVENT_URI)
    result, data = stub_serviceability_collector.collect_data(args=args)
    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert data.rf_events == members
    assert EVENT_URI in data.responses
    assert data.bmc_host == "bmc.example"
    assert data.log_path == "/tmp/serviceability.log"
    redfish_conn_mock.run_get_paged.assert_called_once()


def test_stub_collector_filter_raises_maps_to_error(
    stub_serviceability_collector, redfish_conn_mock
):
    class _BadFilter(_StubServiceabilityCollector):
        def filter_event_members(self, members, args):
            raise ValueError("bad filter")

    collector = _BadFilter(
        system_info=stub_serviceability_collector.system_info,
        connection=redfish_conn_mock,
    )
    redfish_conn_mock.run_get_paged.return_value = RedfishGetResult(
        path=EVENT_URI,
        success=True,
        data={RF_MEMBERS: []},
        status_code=200,
    )
    args = ServiceabilityCollectorArgs(rf_event_log_uri=EVENT_URI)
    result, data = collector.collect_data(args=args)
    assert result.status == ExecutionStatus.ERROR
    assert "Event filter failed" in result.message
    assert data is None


def test_stub_collector_assembly_and_firmware_paths(
    stub_serviceability_collector, redfish_conn_mock
):
    tpl = "/redfish/v1/Chassis/{device}/Assembly"
    asm_uri = tpl.format(device="C1")
    fw_uri = "/redfish/v1/UpdateService/FirmwareInventory"

    def run_get_side_effect(path: str, *_args, **_kwargs):
        if path == EVENT_URI:
            return RedfishGetResult(
                path=EVENT_URI,
                success=True,
                data={RF_MEMBERS: []},
                status_code=200,
            )
        if path == asm_uri:
            return RedfishGetResult(
                path=asm_uri,
                success=True,
                data={"Assemblies": [{"SerialNumber": "SN-ASM"}]},
                status_code=200,
            )
        if path == fw_uri:
            return RedfishGetResult(
                path=fw_uri,
                success=True,
                data={"Details": "fw-summary"},
                status_code=200,
            )
        raise AssertionError(f"unexpected Redfish GET path: {path!r}")

    redfish_conn_mock.run_get.side_effect = run_get_side_effect

    def run_get_paged_forbidden(*_args, **_kwargs):
        raise AssertionError("run_get_paged must not run when follow_next_link=False")

    redfish_conn_mock.run_get_paged.side_effect = run_get_paged_forbidden

    args = ServiceabilityCollectorArgs(
        rf_event_log_uri=EVENT_URI,
        rf_assembly_uri_template=tpl,
        rf_chassis_devices=["C1"],
        rf_firmware_bundle_uri=fw_uri,
        follow_next_link=False,
    )
    result, data = stub_serviceability_collector.collect_data(args=args)
    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert "C1" in data.assembly_info
    assert data.assembly_info["C1"].serial_number == "SN-ASM"
    assert data.component_details == "fw-summary"
    assert asm_uri in data.responses


def test_stub_collector_top_when_count_exceeds_top_uses_skip_and_paged(
    stub_serviceability_collector, redfish_conn_mock
):
    probe = RedfishGetResult(
        path=f"{EVENT_URI}?$top=1",
        success=True,
        data={RF_MEMBERS_COUNT: 100},
        status_code=200,
    )
    window = RedfishGetResult(
        path=f"{EVENT_URI}?$skip=90",
        success=True,
        data={RF_MEMBERS: [{"Id": "last"}]},
        status_code=200,
    )
    redfish_conn_mock.run_get.return_value = probe
    redfish_conn_mock.run_get_paged.return_value = window
    args = ServiceabilityCollectorArgs(rf_event_log_uri=EVENT_URI, top=10)
    result, data = stub_serviceability_collector.collect_data(args=args)
    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert data.rf_events == [{"Id": "last"}]
    redfish_conn_mock.run_get.assert_called_once()
    assert "?$top=1" in redfish_conn_mock.run_get.call_args[0][0]
    redfish_conn_mock.run_get_paged.assert_called_once_with(
        f"{EVENT_URI}?$skip=90", max_pages=args.max_pages
    )


def test_stub_collector_top_when_count_within_top_fetches_full_log(
    stub_serviceability_collector, redfish_conn_mock
):
    probe = RedfishGetResult(
        path=f"{EVENT_URI}?$top=1",
        success=True,
        data={RF_MEMBERS_COUNT: 3},
        status_code=200,
    )
    full = RedfishGetResult(
        path=EVENT_URI,
        success=True,
        data={RF_MEMBERS: [{"Id": "a"}, {"Id": "b"}]},
        status_code=200,
    )
    redfish_conn_mock.run_get.return_value = probe
    redfish_conn_mock.run_get_paged.return_value = full
    args = ServiceabilityCollectorArgs(rf_event_log_uri=EVENT_URI, top=50)
    result, data = stub_serviceability_collector.collect_data(args=args)
    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert len(data.rf_events) == 2
    redfish_conn_mock.run_get_paged.assert_called_once_with(EVENT_URI, max_pages=args.max_pages)


def test_serviceability_data_model_log_model_writes_json(tmp_path):
    model = ServiceabilityDataModel(
        responses={"/x": {"ok": True}},
        cper_data={"slot": {"raw": "data"}},
    )
    model.log_model(str(tmp_path))
    responses_file = tmp_path / "redfish_responses.json"
    cper_file = tmp_path / "cper_data.json"
    assert responses_file.is_file()
    assert cper_file.is_file()
    assert json.loads(responses_file.read_text(encoding="utf-8")) == {"/x": {"ok": True}}
    assert json.loads(cper_file.read_text(encoding="utf-8")) == {"slot": {"raw": "data"}}


def test_serviceability_data_model_log_model_skips_cper_when_empty(tmp_path):
    model = ServiceabilityDataModel(responses={})
    model.log_model(str(tmp_path))
    assert (tmp_path / "redfish_responses.json").is_file()
    assert not (tmp_path / "cper_data.json").exists()
