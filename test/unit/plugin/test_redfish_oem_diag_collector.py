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
from unittest.mock import patch

import pytest

from nodescraper.enums import ExecutionStatus
from nodescraper.plugins.ooband.redfish_oem_diag import (
    RedfishOemDiagCollector,
    RedfishOemDiagCollectorArgs,
    RedfishOemDiagDataModel,
)


@pytest.fixture
def redfish_oem_diag_collector(system_info, redfish_conn_mock):
    return RedfishOemDiagCollector(
        system_info=system_info,
        connection=redfish_conn_mock,
    )


def test_redfish_oem_diag_collector_no_types_configured(redfish_oem_diag_collector):
    result, data = redfish_oem_diag_collector.collect_data()
    assert result.status == ExecutionStatus.NOT_RAN
    assert result.message == "No OEM diagnostic types configured"
    assert data is None


def test_redfish_oem_diag_collector_empty_types_with_args(redfish_oem_diag_collector):
    result, data = redfish_oem_diag_collector.collect_data(
        args=RedfishOemDiagCollectorArgs(oem_diagnostic_types=[])
    )
    assert result.status == ExecutionStatus.NOT_RAN
    assert data is None


@patch("nodescraper.plugins.ooband.redfish_oem_diag.oem_diag_collector.collect_oem_diagnostic_data")
def test_redfish_oem_diag_collector_one_type_success(mock_collect, redfish_oem_diag_collector):
    mock_collect.return_value = (b"log bytes", {"Size": 123}, None)
    result, data = redfish_oem_diag_collector.collect_data(
        args=RedfishOemDiagCollectorArgs(oem_diagnostic_types=["JournalControl"])
    )
    assert result.status == ExecutionStatus.OK
    assert "1/1 types collected" in result.message
    assert data is not None
    assert isinstance(data, RedfishOemDiagDataModel)
    assert "JournalControl" in data.results
    assert data.results["JournalControl"].success is True
    assert data.results["JournalControl"].error is None
    assert data.results["JournalControl"].metadata == {"Size": 123}
    mock_collect.assert_called_once()


@patch("nodescraper.plugins.ooband.redfish_oem_diag.oem_diag_collector.collect_oem_diagnostic_data")
def test_redfish_oem_diag_collector_one_type_failure(mock_collect, redfish_oem_diag_collector):
    mock_collect.return_value = (None, None, "Task timeout")
    result, data = redfish_oem_diag_collector.collect_data(
        args=RedfishOemDiagCollectorArgs(oem_diagnostic_types=["AllLogs"])
    )
    assert result.status == ExecutionStatus.ERROR
    assert "0/1 types collected" in result.message
    assert data is not None
    assert data.results["AllLogs"].success is False
    assert data.results["AllLogs"].error == "Task timeout"


@patch("nodescraper.plugins.ooband.redfish_oem_diag.oem_diag_collector.collect_oem_diagnostic_data")
def test_redfish_oem_diag_collector_mixed_success_fail(mock_collect, redfish_oem_diag_collector):
    def side_effect(conn, log_service_path, oem_diagnostic_type, **kwargs):
        if oem_diagnostic_type == "JournalControl":
            return (b"data", {}, None)
        return (None, None, "Not supported")

    mock_collect.side_effect = side_effect
    result, data = redfish_oem_diag_collector.collect_data(
        args=RedfishOemDiagCollectorArgs(oem_diagnostic_types=["JournalControl", "AllLogs"])
    )
    assert result.status == ExecutionStatus.OK
    assert "1/2 types collected" in result.message
    assert data.results["JournalControl"].success is True
    assert data.results["AllLogs"].success is False
    assert data.results["AllLogs"].error == "Not supported"
    assert mock_collect.call_count == 2


@patch("nodescraper.plugins.ooband.redfish_oem_diag.oem_diag_collector.collect_oem_diagnostic_data")
def test_redfish_oem_diag_collector_passes_args_to_connection(
    mock_collect, redfish_oem_diag_collector, redfish_conn_mock
):
    mock_collect.return_value = (b"", {}, None)
    args = RedfishOemDiagCollectorArgs(
        log_service_path="redfish/v1/Systems/1/LogServices/DiagLogs",
        oem_diagnostic_types=["JournalControl"],
        task_timeout_s=300,
    )
    redfish_oem_diag_collector.collect_data(args=args)
    mock_collect.assert_called_once()
    call_kw = mock_collect.call_args[1]
    assert call_kw["log_service_path"] == "redfish/v1/Systems/1/LogServices/DiagLogs"
    assert call_kw["oem_diagnostic_type"] == "JournalControl"
    assert call_kw["task_timeout_s"] == 300
    assert call_kw["output_dir"] is None
