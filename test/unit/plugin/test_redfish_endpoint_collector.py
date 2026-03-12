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

from nodescraper.connection.redfish import RedfishGetResult
from nodescraper.enums import EventCategory, ExecutionStatus
from nodescraper.plugins.ooband.redfish_endpoint import (
    RedfishEndpointCollector,
    RedfishEndpointCollectorArgs,
)


@pytest.fixture
def redfish_endpoint_collector(system_info, redfish_conn_mock):
    return RedfishEndpointCollector(
        system_info=system_info,
        connection=redfish_conn_mock,
    )


def test_redfish_endpoint_collector_no_uris(redfish_endpoint_collector):
    result, data = redfish_endpoint_collector.collect_data()
    assert result.status == ExecutionStatus.NOT_RAN
    assert result.message == "No Redfish URIs configured"
    assert data is None


def test_redfish_endpoint_collector_no_uris_with_args(redfish_endpoint_collector):
    result, data = redfish_endpoint_collector.collect_data(
        args=RedfishEndpointCollectorArgs(uris=[])
    )
    assert result.status == ExecutionStatus.NOT_RAN
    assert data is None


def test_redfish_endpoint_collector_one_uri_success(redfish_endpoint_collector, redfish_conn_mock):
    redfish_conn_mock.run_get.return_value = RedfishGetResult(
        path="/redfish/v1",
        success=True,
        data={"Name": "Root"},
        status_code=200,
    )
    result, data = redfish_endpoint_collector.collect_data(
        args=RedfishEndpointCollectorArgs(uris=["/redfish/v1"])
    )
    assert result.status == ExecutionStatus.OK
    assert result.message == "Collected 1 Redfish endpoint(s)"
    assert data is not None
    assert data.responses["/redfish/v1"]["Name"] == "Root"
    redfish_conn_mock.run_get.assert_called_once()
    call_path = redfish_conn_mock.run_get.call_args[0][0]
    assert call_path == "/redfish/v1" or call_path.strip("/") == "redfish/v1"


def test_redfish_endpoint_collector_uri_normalized_with_leading_slash(
    redfish_endpoint_collector, redfish_conn_mock
):
    redfish_conn_mock.run_get.return_value = RedfishGetResult(
        path="/redfish/v1/Systems",
        success=True,
        data={"Members": []},
        status_code=200,
    )
    result, data = redfish_endpoint_collector.collect_data(
        args=RedfishEndpointCollectorArgs(uris=["redfish/v1/Systems"])
    )
    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert "/redfish/v1/Systems" in data.responses or "redfish/v1/Systems" in data.responses


def test_redfish_endpoint_collector_one_fail_no_success(
    redfish_endpoint_collector, redfish_conn_mock
):
    redfish_conn_mock.run_get.return_value = RedfishGetResult(
        path="/redfish/v1",
        success=False,
        error="Connection refused",
        status_code=None,
    )
    result, data = redfish_endpoint_collector.collect_data(
        args=RedfishEndpointCollectorArgs(uris=["/redfish/v1"])
    )
    assert result.status == ExecutionStatus.ERROR
    assert result.message.startswith("No Redfish endpoints could be read")
    assert data is None
    assert len(result.events) >= 1
    assert any(
        e.category == EventCategory.RUNTIME.value or "Redfish GET failed" in (e.description or "")
        for e in result.events
    )


def test_redfish_endpoint_collector_mixed_success_fail(
    redfish_endpoint_collector, redfish_conn_mock
):
    def run_get_side_effect(path):
        path_str = str(path)
        if "Systems" in path_str:
            return RedfishGetResult(
                path=path_str if path_str.startswith("/") else "/" + path_str,
                success=True,
                data={"Id": "1"},
                status_code=200,
            )
        return RedfishGetResult(
            path=path_str if path_str.startswith("/") else "/" + path_str,
            success=False,
            error="Not Found",
            status_code=404,
        )

    redfish_conn_mock.run_get.side_effect = run_get_side_effect
    result, data = redfish_endpoint_collector.collect_data(
        args=RedfishEndpointCollectorArgs(uris=["/redfish/v1/Systems", "/redfish/v1/Bad"])
    )
    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert len(data.responses) == 1
    keys = list(data.responses.keys())
    assert any("Systems" in k for k in keys)
    assert list(data.responses.values())[0].get("Id") == "1"
