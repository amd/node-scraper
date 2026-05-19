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
from typing import Optional

import pytest
from pydantic import ValidationError

from nodescraper.base import OOBandDataPlugin
from nodescraper.connection.redfish import RedfishConnectionManager
from nodescraper.enums import ExecutionStatus
from nodescraper.plugins.serviceability import (
    OobRedfishCollector,
    OobRedfishCollectorArgs,
    OobRedfishDataModel,
    OobRedfishDeviceInfo,
    OobRedfishPlugin,
    OobRedfishResult,
    build_oob_redfish_reporting_version_fields,
    compare_iso_datetime,
    is_valid_iso_datetime,
    satisfies_time_check,
)

EVENT_URI = "/redfish/v1/Systems/1/LogServices/SEL/Entries"


class _StubOobRedfishCollector(OobRedfishCollector):
    def collect_data(self, args: Optional[OobRedfishCollectorArgs] = None):
        if args is None:
            return self._missing_args_result()
        data = OobRedfishDataModel(
            collected_data={"events": []},
            log_path=self._log_path,
        )
        self.result.status = ExecutionStatus.OK
        self.result.message = "stub collection complete"
        return self.result, data


@pytest.fixture
def stub_oob_redfish_collector(system_info, redfish_conn_mock):
    return _StubOobRedfishCollector(
        system_info=system_info,
        connection=redfish_conn_mock,
        log_path="/tmp/oob_redfish.log",
    )


def test_oob_redfish_collector_args_requires_event_log_uri():
    with pytest.raises(ValidationError):
        OobRedfishCollectorArgs()


def test_oob_redfish_collector_args_uri_alias():
    args = OobRedfishCollectorArgs(uri=" /events ", rf_event_log_uri="/other")
    assert args.resolved_event_log_uri() == "/events"


def test_oob_redfish_collector_args_assembly_requires_both_template_and_devices():
    with pytest.raises(ValidationError):
        OobRedfishCollectorArgs(
            rf_event_log_uri=EVENT_URI,
            rf_assembly_uri_template="/redfish/v1/Chassis/{device}/Assembly",
        )
    with pytest.raises(ValidationError):
        OobRedfishCollectorArgs(
            rf_event_log_uri=EVENT_URI,
            rf_chassis_devices=["C1"],
        )


def test_oob_redfish_collector_args_reference_time_requires_operator():
    with pytest.raises(ValidationError):
        OobRedfishCollectorArgs(
            rf_event_log_uri=EVENT_URI,
            reference_time="2026-05-17",
        )


def test_oob_redfish_collector_args_accepts_iso_date_and_datetime():
    date_args = OobRedfishCollectorArgs(
        rf_event_log_uri=EVENT_URI,
        reference_time="2026-05-17",
        time_operator=">=",
    )
    assert date_args.reference_time == "2026-05-17"


def test_time_utils_iso_validation_and_comparison():
    assert is_valid_iso_datetime("2026-05-17")
    assert satisfies_time_check("2026-05-18", "2026-05-17", ">")
    assert compare_iso_datetime("2026-05-17T13:01:00", "2026-05-17T13:01:00", "==")


def test_oob_redfish_plugin_wiring():
    assert issubclass(OobRedfishPlugin, OOBandDataPlugin)
    assert OobRedfishPlugin.DATA_MODEL is OobRedfishDataModel
    assert OobRedfishPlugin.COLLECTOR is OobRedfishCollector
    assert OobRedfishPlugin.COLLECTOR_ARGS is OobRedfishCollectorArgs
    assert OobRedfishPlugin.CONNECTION_TYPE is RedfishConnectionManager
    assert OobRedfishPlugin.ANALYZER is None


def test_stub_collector_no_args(stub_oob_redfish_collector):
    result, data = stub_oob_redfish_collector.collect_data()
    assert result.status == ExecutionStatus.NOT_RAN
    assert "required" in result.message.lower()
    assert data is None


def test_stub_collector_success_minimal(stub_oob_redfish_collector):
    args = OobRedfishCollectorArgs(rf_event_log_uri=EVENT_URI)
    result, data = stub_oob_redfish_collector.collect_data(args=args)
    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert data.collected_data == {"events": []}


def test_collector_satisfies_reference_time_helper(stub_oob_redfish_collector):
    args = OobRedfishCollectorArgs(
        rf_event_log_uri=EVENT_URI,
        reference_time="2026-05-17",
        time_operator=">=",
    )
    assert stub_oob_redfish_collector.satisfies_reference_time("2026-05-18", args)
    assert not stub_oob_redfish_collector.satisfies_reference_time("2026-05-16", args)


def test_oob_redfish_device_info_fields():
    info = OobRedfishDeviceInfo(
        board_product_name="Board-A",
        board_serial_number="BSN-1",
        product_version="1.0",
    )
    assert info.board_product_name == "Board-A"
    assert info.product_version == "1.0"


def test_oob_redfish_result_reporting_versions():
    version_fields = build_oob_redfish_reporting_version_fields(
        plugin_name="example_oob_redfish",
        plugin_version="0.1.0",
        node_scraper_version="1.2.3",
        isa_version="9.8.7",
    )
    result = OobRedfishResult(node="node-1", **version_fields)
    assert result.plugin_name == "example_oob_redfish"
    assert result.reporter_extensions["isa_version"] == "9.8.7"


def test_oob_redfish_data_model_log_model(tmp_path):
    model = OobRedfishDataModel(
        collected_data={"events": [{"id": 1}]},
        artifacts={"events.json": [{"id": 1}]},
    )
    model.log_model(str(tmp_path))
    assert (tmp_path / "events.json").is_file()
    assert (tmp_path / "oob_redfish_data.json").is_file()
