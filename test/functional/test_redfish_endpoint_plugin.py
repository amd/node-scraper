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
from unittest.mock import MagicMock

import pytest

from nodescraper.connection.redfish import RedfishGetResult
from nodescraper.enums import EventCategory, ExecutionStatus
from nodescraper.plugins.ooband.redfish_endpoint import (
    RedfishEndpointCollector,
    RedfishEndpointCollectorArgs,
)
from nodescraper.plugins.ooband.redfish_endpoint import endpoint_collector as ec


@pytest.fixture
def redfish_endpoint_collector(system_info, redfish_conn_mock):
    return RedfishEndpointCollector(
        system_info=system_info,
        connection=redfish_conn_mock,
    )


def test_redfish_endpoint_collector_no_uris(redfish_endpoint_collector):
    result, data = redfish_endpoint_collector.collect_data()
    assert result.status == ExecutionStatus.NOT_RAN
    assert (
        result.message
        == "No collection mode configured: set collection_args.discover_tree to true or provide collection_args.uris"
    )
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


def test_normalize_path_empty_or_invalid():
    api = "redfish/v1"
    assert ec._normalize_path("", api) == ""
    assert ec._normalize_path(None, api) == ""  # type: ignore[arg-type]
    assert ec._normalize_path("  ", api) == ""


def test_normalize_path_relative_path():
    api = "redfish/v1"
    assert ec._normalize_path("/redfish/v1", api) == "/redfish/v1"
    assert ec._normalize_path("/redfish/v1/", api) == "/redfish/v1"
    assert ec._normalize_path("redfish/v1/Systems", api) == "/redfish/v1/Systems"
    assert ec._normalize_path("  /redfish/v1/Chassis  ", api) == "/redfish/v1/Chassis"


def test_normalize_path_full_url():
    api = "redfish/v1"
    assert ec._normalize_path("https://host/redfish/v1/Systems", api) == "/redfish/v1/Systems"
    assert ec._normalize_path("http://bmc/redfish/v1", api) == "/redfish/v1"


def test_normalize_path_outside_api_root():
    api = "redfish/v1"
    assert ec._normalize_path("/other/root", api) == ""
    assert ec._normalize_path("https://host/other/path", api) == ""


def test_extract_odata_ids_empty():
    assert ec._extract_odata_ids({}) == []
    assert ec._extract_odata_ids([]) == []
    assert ec._extract_odata_ids("x") == []


def test_extract_odata_ids_single():
    assert ec._extract_odata_ids({"@odata.id": "/redfish/v1"}) == ["/redfish/v1"]
    assert ec._extract_odata_ids({"@odata.id": "https://host/redfish/v1"}) == [
        "https://host/redfish/v1"
    ]


def test_extract_odata_ids_members():
    body = {
        "Members": [
            {"@odata.id": "/redfish/v1/Systems/1"},
            {"@odata.id": "/redfish/v1/Systems/2"},
        ]
    }
    assert set(ec._extract_odata_ids(body)) == {"/redfish/v1/Systems/1", "/redfish/v1/Systems/2"}


def test_extract_odata_ids_nested_and_members():
    body = {
        "@odata.id": "/redfish/v1",
        "Systems": {"@odata.id": "/redfish/v1/Systems", "Members": []},
        "Chassis": {
            "Members": [{"@odata.id": "/redfish/v1/Chassis/1"}],
        },
    }
    ids = ec._extract_odata_ids(body)
    assert "/redfish/v1" in ids
    assert "/redfish/v1/Systems" in ids
    assert "/redfish/v1/Chassis/1" in ids


def test_uris_from_args_none():
    assert ec._uris_from_args(None) == []


def test_uris_from_args_empty():
    assert ec._uris_from_args(RedfishEndpointCollectorArgs(uris=[])) == []


def test_uris_from_args_with_uris():
    args = RedfishEndpointCollectorArgs(uris=["/redfish/v1", "/redfish/v1/Systems"])
    assert ec._uris_from_args(args) == ["/redfish/v1", "/redfish/v1/Systems"]


def test_fetch_one_calls_run_get():
    conn = MagicMock()
    conn.run_get.return_value = RedfishGetResult(
        path="/redfish/v1", success=True, data={}, status_code=200
    )
    out = ec._fetch_one(conn, "/redfish/v1")
    conn.run_get.assert_called_once_with("/redfish/v1")
    assert out.success is True
    assert out.path == "/redfish/v1"


def test_discover_tree_single_root():
    conn = MagicMock()
    conn.run_get.return_value = RedfishGetResult(
        path="/redfish/v1",
        success=True,
        data={"@odata.id": "/redfish/v1", "Name": "Root"},
        status_code=200,
    )
    paths, responses, results = ec._discover_tree(
        conn, api_root="redfish/v1", max_depth=2, max_endpoints=0
    )
    assert paths == ["/redfish/v1"]
    assert list(responses.keys()) == ["/redfish/v1"]
    assert responses["/redfish/v1"]["Name"] == "Root"
    assert len(results) == 1
    conn.run_get.assert_called_once_with("/redfish/v1")


def test_discover_tree_follows_links():
    conn = MagicMock()
    root_data = {
        "@odata.id": "/redfish/v1",
        "Systems": {"@odata.id": "/redfish/v1/Systems"},
    }
    systems_data = {
        "@odata.id": "/redfish/v1/Systems",
        "Members": [{"@odata.id": "/redfish/v1/Systems/1"}],
    }
    system1_data = {"@odata.id": "/redfish/v1/Systems/1", "Id": "1"}

    def run_get(path):
        if path == "/redfish/v1":
            return RedfishGetResult(path=path, success=True, data=root_data, status_code=200)
        if path == "/redfish/v1/Systems":
            return RedfishGetResult(path=path, success=True, data=systems_data, status_code=200)
        if path == "/redfish/v1/Systems/1":
            return RedfishGetResult(path=path, success=True, data=system1_data, status_code=200)
        return RedfishGetResult(path=path, success=False, error="Not Found", status_code=404)

    conn.run_get.side_effect = run_get
    paths, responses, results = ec._discover_tree(
        conn, api_root="redfish/v1", max_depth=3, max_endpoints=0
    )
    assert "/redfish/v1" in paths
    assert "/redfish/v1/Systems" in paths
    assert "/redfish/v1/Systems/1" in paths
    assert responses["/redfish/v1"]["@odata.id"] == "/redfish/v1"
    assert responses["/redfish/v1/Systems"]["@odata.id"] == "/redfish/v1/Systems"
    assert responses["/redfish/v1/Systems/1"]["Id"] == "1"
    assert len(results) >= 3


def test_discover_tree_respects_max_depth():
    conn = MagicMock()
    root_data = {"@odata.id": "/redfish/v1", "Systems": {"@odata.id": "/redfish/v1/Systems"}}
    systems_data = {
        "@odata.id": "/redfish/v1/Systems",
        "Members": [{"@odata.id": "/redfish/v1/Systems/1"}],
    }

    def run_get(path):
        if path == "/redfish/v1":
            return RedfishGetResult(path=path, success=True, data=root_data, status_code=200)
        if path == "/redfish/v1/Systems":
            return RedfishGetResult(path=path, success=True, data=systems_data, status_code=200)
        return RedfishGetResult(path=path, success=True, data={}, status_code=200)

    conn.run_get.side_effect = run_get
    paths, responses, results = ec._discover_tree(
        conn, api_root="redfish/v1", max_depth=1, max_endpoints=0
    )
    assert "/redfish/v1" in paths
    assert "/redfish/v1/Systems" not in paths
    assert len(responses) == 1


def test_discover_tree_respects_max_endpoints():
    conn = MagicMock()
    conn.run_get.return_value = RedfishGetResult(
        path="/redfish/v1",
        success=True,
        data={"@odata.id": "/redfish/v1", "Systems": {"@odata.id": "/redfish/v1/Systems"}},
        status_code=200,
    )
    paths, responses, results = ec._discover_tree(
        conn, api_root="redfish/v1", max_depth=5, max_endpoints=1
    )
    assert len(paths) == 1
    assert len(responses) == 1
    conn.run_get.assert_called_once()


def test_collect_data_discover_tree_success(redfish_endpoint_collector, redfish_conn_mock):
    redfish_conn_mock.api_root = "redfish/v1"
    redfish_conn_mock.run_get.return_value = RedfishGetResult(
        path="/redfish/v1",
        success=True,
        data={"@odata.id": "/redfish/v1", "Name": "Root"},
        status_code=200,
    )
    result, data = redfish_endpoint_collector.collect_data(
        args=RedfishEndpointCollectorArgs(discover_tree=True)
    )
    assert result.status == ExecutionStatus.OK
    assert result.message == "Collected 1 Redfish endpoint(s) from tree"
    assert data is not None
    assert "/redfish/v1" in data.responses
    assert data.responses["/redfish/v1"]["Name"] == "Root"


def test_collect_data_discover_tree_no_responses(redfish_endpoint_collector, redfish_conn_mock):
    redfish_conn_mock.api_root = "redfish/v1"
    redfish_conn_mock.run_get.return_value = RedfishGetResult(
        path="/redfish/v1", success=False, error="Connection refused", status_code=None
    )
    result, data = redfish_endpoint_collector.collect_data(
        args=RedfishEndpointCollectorArgs(discover_tree=True)
    )
    assert result.status == ExecutionStatus.ERROR
    assert "No Redfish endpoints discovered from tree" in result.message
    assert data is None


def test_collect_data_concurrent_two_uris(redfish_endpoint_collector, redfish_conn_mock):
    redfish_conn_mock.copy.return_value = redfish_conn_mock
    call_count = 0

    def run_get(path):
        nonlocal call_count
        call_count += 1
        return RedfishGetResult(
            path=path if path.startswith("/") else "/" + path,
            success=True,
            data={"path": path},
            status_code=200,
        )

    redfish_conn_mock.run_get.side_effect = run_get
    result, data = redfish_endpoint_collector.collect_data(
        args=RedfishEndpointCollectorArgs(
            uris=["/redfish/v1", "/redfish/v1/Systems"], max_workers=2
        )
    )
    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert len(data.responses) == 2
    assert "/redfish/v1" in data.responses or "redfish/v1" in data.responses
    assert any("Systems" in k for k in data.responses)
    assert redfish_conn_mock.copy.called
