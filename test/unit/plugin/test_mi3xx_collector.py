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
import pytest
from pydantic import ValidationError
from serviceability_dummy_data import (
    DUMMY_BMC_HOST,
    DUMMY_CPER_BYTES_BASIC,
    DUMMY_CPER_BYTES_RF,
    DUMMY_CPER_EVENT_ID_BASIC,
    DUMMY_CPER_EVENT_ID_RF,
    DUMMY_EVENT_URI,
    DUMMY_EVENT_URI_ALT,
    DUMMY_TIMESTAMP_EARLIER,
    DUMMY_TIMESTAMP_LATER,
    dummy_cper_basic_member,
    dummy_cper_rf_member,
    dummy_cper_skip_member,
)

from nodescraper.connection.redfish import RF_MEMBERS, RedfishGetResult
from nodescraper.enums import ExecutionStatus
from nodescraper.plugins.serviceability import (
    MI3XXAnalyzer,
    MI3XXCollector,
    MI3XXCollectorArgs,
    MI3XXDataModel,
    MI3XXDeviceInfo,
    MI3XXResult,
    ServiceabilityDataModel,
    ServiceabilityPluginBase,
    ServiceabilityPluginMI3XX,
    build_mi3xx_reporting_version_fields,
    compare_iso_datetime,
    is_valid_iso_datetime,
    satisfies_time_check,
)

EVENT_URI = DUMMY_EVENT_URI


@pytest.fixture
def mi3xx_collector(system_info, redfish_conn_mock):
    redfish_conn_mock.base_url = f"https://{DUMMY_BMC_HOST}/redfish/v1"
    return MI3XXCollector(
        system_info=system_info,
        connection=redfish_conn_mock,
        log_path="/tmp/mi3xx.log",
    )


def test_mi3xx_collector_args_default_event_log_uri():
    args = MI3XXCollectorArgs()
    uri = args.resolved_event_log_uri()
    assert uri == MI3XXCollectorArgs.default_event_log_uri()
    assert uri.startswith("/redfish/")
    assert "EventLog" in uri


def test_mi3xx_collector_args_requires_event_log_uri():
    with pytest.raises(ValidationError):
        MI3XXCollectorArgs(uri="", rf_event_log_uri="")


def test_mi3xx_collector_args_uri_alias_prefers_uri_when_both_set():
    args = MI3XXCollectorArgs(
        uri=f" {DUMMY_EVENT_URI_ALT} ",
        rf_event_log_uri=DUMMY_EVENT_URI,
    )
    assert args.resolved_event_log_uri() == DUMMY_EVENT_URI_ALT


def test_mi3xx_collector_args_strips_rf_event_log_uri():
    args = MI3XXCollectorArgs(rf_event_log_uri=f"  {DUMMY_EVENT_URI_ALT}  ")
    assert args.rf_event_log_uri == DUMMY_EVENT_URI_ALT
    assert args.resolved_event_log_uri() == DUMMY_EVENT_URI_ALT


def test_mi3xx_collector_args_assembly_requires_both_template_and_devices():
    with pytest.raises(ValidationError):
        MI3XXCollectorArgs(
            rf_event_log_uri=EVENT_URI,
            rf_assembly_uri_template="/redfish/v1/Chassis/{device}/Assembly",
        )
    with pytest.raises(ValidationError):
        MI3XXCollectorArgs(
            rf_event_log_uri=EVENT_URI,
            rf_chassis_devices=["dummy-chassis"],
        )


def test_mi3xx_collector_args_reference_time_requires_operator():
    with pytest.raises(ValidationError):
        MI3XXCollectorArgs(
            rf_event_log_uri=EVENT_URI,
            reference_time="2000-01-01",
        )


def test_mi3xx_collector_args_accepts_iso_date_and_datetime():
    date_args = MI3XXCollectorArgs(
        rf_event_log_uri=EVENT_URI,
        reference_time="2000-01-01",
        time_operator=">=",
    )
    assert date_args.reference_time == "2000-01-01"


def test_time_utils_iso_validation_and_comparison():
    assert is_valid_iso_datetime("2000-01-01")
    assert satisfies_time_check("2000-01-02", "2000-01-01", ">")
    assert compare_iso_datetime("2000-01-01T00:00:00", "2000-01-01T00:00:00", "==")


def test_serviceability_plugin_mi3xx_wiring():
    assert issubclass(ServiceabilityPluginMI3XX, ServiceabilityPluginBase)
    assert ServiceabilityPluginMI3XX.DATA_MODEL is ServiceabilityDataModel
    assert ServiceabilityPluginMI3XX.COLLECTOR is MI3XXCollector
    assert ServiceabilityPluginMI3XX.COLLECTOR_ARGS is MI3XXCollectorArgs
    assert ServiceabilityPluginMI3XX.ANALYZER is MI3XXAnalyzer
    assert MI3XXCollector.DOCUMENTATION_COLLECTION_ITEMS
    assert MI3XXAnalyzer.DOCUMENTATION_ANALYSIS_ITEMS


def test_mi3xx_collector_no_args(mi3xx_collector):
    result, data = mi3xx_collector.collect_data()
    assert result.status == ExecutionStatus.NOT_RAN
    assert "required" in result.message.lower()
    assert data is None


def test_mi3xx_collector_success_minimal(mi3xx_collector, redfish_conn_mock):
    redfish_conn_mock.run_get_paged.return_value = RedfishGetResult(
        path=EVENT_URI,
        success=True,
        data={RF_MEMBERS: [{"Id": "dummy-1", "Created": DUMMY_TIMESTAMP_LATER}]},
        status_code=200,
    )
    args = MI3XXCollectorArgs(rf_event_log_uri=EVENT_URI)
    result, data = mi3xx_collector.collect_data(args=args)
    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert len(data.rf_events) == 1
    assert data.bmc_host == DUMMY_BMC_HOST
    assert data.log_path == "/tmp/mi3xx.log"


def test_mi3xx_collector_satisfies_reference_time_helper(mi3xx_collector):
    args = MI3XXCollectorArgs(
        rf_event_log_uri=EVENT_URI,
        reference_time="2000-01-01",
        time_operator=">=",
    )
    assert mi3xx_collector.satisfies_reference_time(DUMMY_TIMESTAMP_LATER, args)
    assert not mi3xx_collector.satisfies_reference_time(DUMMY_TIMESTAMP_EARLIER, args)


def test_mi3xx_collector_is_cper_event_requires_cper_block_type_and_uri(mi3xx_collector):
    assert mi3xx_collector.is_cper_event(dummy_cper_basic_member())
    assert not mi3xx_collector.is_cper_event(
        {
            "Id": "non-cper",
            "AdditionalDataURI": DUMMY_EVENT_URI,
            "MessageId": "ResourceEvent.1.2.1.ResourceErrorsDetectedOEM",
        }
    )
    assert not mi3xx_collector.is_cper_event(
        {
            "Id": "partial-cper",
            "CPER": {"NotificationType": "dummy"},
            "DiagnosticDataType": "CPER",
        }
    )


def test_mi3xx_collector_fetches_cper_attachments(mi3xx_collector, redfish_conn_mock):
    import base64
    from unittest.mock import MagicMock

    redfish_conn_mock.run_get_paged.return_value = RedfishGetResult(
        path=EVENT_URI,
        success=True,
        data={RF_MEMBERS: [dummy_cper_basic_member()]},
        status_code=200,
    )
    response = MagicMock()
    response.ok = True
    response.status_code = 200
    response.content = DUMMY_CPER_BYTES_BASIC
    redfish_conn_mock.get_response.return_value = response

    args = MI3XXCollectorArgs(rf_event_log_uri=EVENT_URI)
    result, data = mi3xx_collector.collect_data(args=args)
    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert data.cper_raw[DUMMY_CPER_EVENT_ID_BASIC] == base64.b64encode(
        DUMMY_CPER_BYTES_BASIC
    ).decode("ascii")
    assert data.cper_data == {}


def test_mi3xx_collector_skips_cper_when_aca_serial_and_low_afids(
    mi3xx_collector, redfish_conn_mock
):
    redfish_conn_mock.get_response.reset_mock()
    redfish_conn_mock.run_get_paged.return_value = RedfishGetResult(
        path=EVENT_URI,
        success=True,
        data={RF_MEMBERS: [dummy_cper_skip_member()]},
        status_code=200,
    )
    args = MI3XXCollectorArgs(rf_event_log_uri=EVENT_URI)
    result, data = mi3xx_collector.collect_data(args=args)
    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert data.cper_raw == {}
    redfish_conn_mock.get_response.assert_not_called()


def test_mi3xx_collector_fetches_cper_when_rf_afid(mi3xx_collector, redfish_conn_mock):
    import base64
    from unittest.mock import MagicMock

    redfish_conn_mock.get_response.reset_mock()
    redfish_conn_mock.run_get_paged.return_value = RedfishGetResult(
        path=EVENT_URI,
        success=True,
        data={RF_MEMBERS: [dummy_cper_rf_member()]},
        status_code=200,
    )
    response = MagicMock()
    response.ok = True
    response.status_code = 200
    response.content = DUMMY_CPER_BYTES_RF
    redfish_conn_mock.get_response.return_value = response

    args = MI3XXCollectorArgs(rf_event_log_uri=EVENT_URI)
    result, data = mi3xx_collector.collect_data(args=args)
    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert data.cper_raw[DUMMY_CPER_EVENT_ID_RF] == base64.b64encode(DUMMY_CPER_BYTES_RF).decode(
        "ascii"
    )
    redfish_conn_mock.get_response.assert_called_once()


def test_mi3xx_collector_filters_events_by_reference_time(mi3xx_collector, redfish_conn_mock):
    redfish_conn_mock.run_get_paged.return_value = RedfishGetResult(
        path=EVENT_URI,
        success=True,
        data={
            RF_MEMBERS: [
                {"Id": "dummy-1", "Created": DUMMY_TIMESTAMP_LATER},
                {"Id": "dummy-2", "Created": DUMMY_TIMESTAMP_EARLIER},
            ]
        },
        status_code=200,
    )
    args = MI3XXCollectorArgs(
        rf_event_log_uri=EVENT_URI,
        reference_time="2000-01-01",
        time_operator=">=",
    )
    result, data = mi3xx_collector.collect_data(args=args)
    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert [event["Id"] for event in data.rf_events] == ["dummy-1"]


def test_mi3xx_device_info_fields():
    info = MI3XXDeviceInfo(
        board_product_name="dummy-board",
        board_serial_number="dummy-serial-001",
        product_version="0.0-dummy",
    )
    assert info.board_product_name == "dummy-board"
    assert info.product_version == "0.0-dummy"


def test_mi3xx_result_reporting_versions():
    version_fields = build_mi3xx_reporting_version_fields(
        plugin_name="dummy_plugin",
        plugin_version="0.0-dummy",
        node_scraper_version="0.0-dummy",
        dummy_hub_version="0.0-dummy",
    )
    result = MI3XXResult(node="dummy-node", **version_fields)
    assert result.plugin_name == "dummy_plugin"
    assert result.reporter_extensions["dummy_hub_version"] == "0.0-dummy"


def test_mi3xx_data_model_log_model(tmp_path):
    model = MI3XXDataModel(
        collected_data={"events": [{"id": 1}]},
        artifacts={"events.json": [{"id": 1}]},
    )
    model.log_model(str(tmp_path))
    assert (tmp_path / "events.json").is_file()
    assert (tmp_path / "MI3XX_data.json").is_file()
