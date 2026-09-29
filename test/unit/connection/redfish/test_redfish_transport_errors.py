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
import socket
from unittest.mock import MagicMock, patch

import pytest
import requests
from pydantic import SecretStr

from nodescraper.connection.redfish import RedfishConnection, RedfishConnectionError
from nodescraper.connection.redfish.redfish_manager import RedfishConnectionManager
from nodescraper.connection.redfish.redfish_params import RedfishConnectionParams
from nodescraper.enums import ExecutionStatus, SystemLocation
from nodescraper.models import SystemInfo

_TEST_HOST = "10.6.189.112"


@pytest.fixture
def rf_conn() -> RedfishConnection:
    return RedfishConnection(
        base_url=f"https://{_TEST_HOST}",
        username="user",
        password="pass",
        use_session_auth=False,
    )


def test_get_response_wraps_connect_timeout(rf_conn: RedfishConnection) -> None:
    with patch.object(rf_conn, "_ensure_session") as ensure_session:
        session = MagicMock()
        session.get.side_effect = requests.exceptions.ConnectTimeout("timed out")
        ensure_session.return_value = session

        with pytest.raises(RedfishConnectionError, match="timed out"):
            rf_conn.get_response("redfish/v1")


def test_get_response_wraps_connection_refused(rf_conn: RedfishConnection) -> None:
    root = ConnectionRefusedError(111, "Connection refused")
    wrapped = requests.exceptions.ConnectionError("failed", response=None)
    wrapped.__cause__ = root

    with patch.object(rf_conn, "_ensure_session") as ensure_session:
        session = MagicMock()
        session.get.side_effect = wrapped
        ensure_session.return_value = session

        with pytest.raises(RedfishConnectionError, match="connection failed"):
            rf_conn.get_response("redfish/v1")


def test_get_response_wraps_name_resolution_error(rf_conn: RedfishConnection) -> None:
    dns_error = requests.exceptions.ConnectionError(
        f"HTTPSConnectionPool(host='{_TEST_HOST}', port=443): "
        f"Failed to resolve '{_TEST_HOST}' "
        "([Errno -5] No address associated with hostname)"
    )
    dns_error.__cause__ = socket.gaierror(-5, "No address associated with hostname")

    with patch.object(rf_conn, "_ensure_session") as ensure_session:
        session = MagicMock()
        session.get.side_effect = dns_error
        ensure_session.return_value = session

        with pytest.raises(RedfishConnectionError, match="hostname could not be resolved"):
            rf_conn.get_response("redfish/v1")


def test_redfish_manager_connect_logs_clean_timeout() -> None:
    manager = RedfishConnectionManager(
        system_info=SystemInfo(name="test", location=SystemLocation.LOCAL),
        connection_args=RedfishConnectionParams(
            host=_TEST_HOST,
            username="user",
            password=SecretStr("pass"),
            use_https=True,
            use_session_auth=False,
        ),
    )
    with patch(
        "nodescraper.connection.redfish.redfish_manager.RedfishConnection"
    ) as connection_cls:
        connection = connection_cls.return_value
        connection.get_service_root.side_effect = RedfishConnectionError(
            f"Redfish connection timed out: {_TEST_HOST}"
        )

        result = manager.connect()

    assert result.status == ExecutionStatus.EXECUTION_FAILURE
    assert len(result.events) == 1
    assert "timed out" in result.events[0].description
    assert "traceback" not in result.events[0].data
    assert "exception_type" not in result.events[0].data
