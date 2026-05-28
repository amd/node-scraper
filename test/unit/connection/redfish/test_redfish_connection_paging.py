###############################################################################
#
# MIT License
#
# Copyright (C) 2026 Advanced Micro Devices, Inc.
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

from nodescraper.connection.redfish import (
    RF_MEMBERS,
    RF_MEMBERS_COUNT,
    RF_MEMBERS_NEXT_LINK,
    RedfishConnection,
    RedfishGetResult,
)


@pytest.fixture
def rf_conn() -> RedfishConnection:
    return RedfishConnection(
        base_url="https://bmc.example",
        username="u",
        password="p",
        verify_ssl=False,
    )


def test_run_get_paged_no_next_link_returns_first_unchanged(rf_conn: RedfishConnection) -> None:
    first_body = {RF_MEMBERS: [{"x": 1}], "Name": "Col"}
    first = RedfishGetResult(
        path="/redfish/v1/Systems",
        success=True,
        data=first_body,
        status_code=200,
    )
    with patch.object(rf_conn, "run_get", return_value=first) as mock_get:
        out = rf_conn.run_get_paged("/redfish/v1/Systems")

    mock_get.assert_called_once()
    assert out.success is True
    assert out.data == first_body
    assert RF_MEMBERS_NEXT_LINK not in out.data


def test_run_get_paged_merges_members_and_strips_next_link(rf_conn: RedfishConnection) -> None:
    page1 = {
        RF_MEMBERS: [{"@odata.id": "/1"}],
        RF_MEMBERS_NEXT_LINK: "/redfish/v1/Systems?$skip=1",
        f"{RF_MEMBERS}@odata.count": 99,
    }
    page2 = {
        RF_MEMBERS: [{"@odata.id": "/2"}],
    }

    def fake_get(path: str) -> RedfishGetResult:
        p = str(path).strip()
        if not p.startswith("/"):
            p = "/" + p
        if "skip" not in p:
            return RedfishGetResult(
                path="/redfish/v1/Systems", success=True, data=page1, status_code=200
            )
        return RedfishGetResult(path=p, success=True, data=page2, status_code=200)

    with patch.object(rf_conn, "run_get", side_effect=fake_get):
        out = rf_conn.run_get_paged("/redfish/v1/Systems", max_pages=10)

    assert out.success is True
    assert out.path == "/redfish/v1/Systems"
    assert out.data is not None
    assert out.data[RF_MEMBERS] == [{"@odata.id": "/1"}, {"@odata.id": "/2"}]
    assert out.data[RF_MEMBERS_COUNT] == 2
    assert RF_MEMBERS_NEXT_LINK not in out.data


def test_run_get_paged_stops_on_followup_failure_keeps_partial_merge(
    rf_conn: RedfishConnection,
) -> None:
    page1 = {
        RF_MEMBERS: [{"@odata.id": "/1"}],
        RF_MEMBERS_NEXT_LINK: "/next",
    }

    def fake_get(path: str) -> RedfishGetResult:
        ps = str(path)
        if "next" not in ps:
            return RedfishGetResult(path="/col", success=True, data=page1, status_code=200)
        return RedfishGetResult(path="/next", success=False, error="timeout", status_code=None)

    with patch.object(rf_conn, "run_get", side_effect=fake_get):
        out = rf_conn.run_get_paged("/col")

    assert out.success is True
    assert out.data is not None
    assert out.data[RF_MEMBERS] == [{"@odata.id": "/1"}]
    assert RF_MEMBERS_NEXT_LINK not in out.data


def test_run_get_paged_respects_max_pages(rf_conn: RedfishConnection) -> None:
    """max_pages=2 allows initial GET plus one nextLink follow only."""

    def body_with_next(mid: str) -> dict:
        return {
            RF_MEMBERS: [{"id": mid}],
            RF_MEMBERS_NEXT_LINK: "/page2",
        }

    calls: list[str] = []

    def fake_get(path: str) -> RedfishGetResult:
        calls.append(str(path))
        ps = str(path)
        if len(calls) == 1:
            return RedfishGetResult(
                path="/start", success=True, data=body_with_next("a"), status_code=200
            )
        return RedfishGetResult(path=ps, success=True, data=body_with_next("b"), status_code=200)

    with patch.object(rf_conn, "run_get", side_effect=fake_get):
        out = rf_conn.run_get_paged("/start", max_pages=2)

    assert len(calls) == 2
    assert out.data is not None
    assert len(out.data[RF_MEMBERS]) == 2
    assert RF_MEMBERS_NEXT_LINK not in out.data


def test_run_get_paged_first_request_failure_passthrough(rf_conn: RedfishConnection) -> None:
    err = RedfishGetResult(
        path="/redfish/v1/Bad",
        success=False,
        error="nope",
        status_code=404,
    )
    with patch.object(rf_conn, "run_get", return_value=err):
        out = rf_conn.run_get_paged("/redfish/v1/Bad")

    assert out is err
    assert out.success is False
