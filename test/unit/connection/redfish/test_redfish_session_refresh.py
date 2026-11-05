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
from unittest.mock import MagicMock, patch

import pytest

from nodescraper.connection.redfish import RedfishConnection, RedfishConnectionError


def _response(status_code: int) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.ok = status_code < 400
    return response


@pytest.fixture
def session_conn() -> RedfishConnection:
    return RedfishConnection(
        base_url="https://bmc.example",
        username="root",
        password="pass",
        use_session_auth=True,
        verify_ssl=False,
    )


def test_get_response_refreshes_session_after_401(session_conn: RedfishConnection) -> None:
    stale = MagicMock()
    fresh = MagicMock()
    stale.get.return_value = _response(401)
    fresh.get.return_value = _response(200)
    sessions = [stale, fresh]

    def ensure_session() -> MagicMock:
        session_conn._session = sessions.pop(0)
        return session_conn._session

    with patch.object(session_conn, "_ensure_session", side_effect=ensure_session):
        response = session_conn.get_response("/redfish/v1/Systems")

    assert response.status_code == 200
    stale.get.assert_called_once()
    fresh.get.assert_called_once()
    assert session_conn._session is fresh


def test_get_response_returns_second_401_after_refresh(session_conn: RedfishConnection) -> None:
    stale = MagicMock()
    fresh = MagicMock()
    stale.get.return_value = _response(401)
    second = _response(401)
    fresh.get.return_value = second
    sessions = [stale, fresh]

    def ensure_session() -> MagicMock:
        session_conn._session = sessions.pop(0)
        return session_conn._session

    with patch.object(session_conn, "_ensure_session", side_effect=ensure_session):
        response = session_conn.get_response("/redfish/v1/Systems")

    assert response is second
    assert fresh.get.call_count == 1


def test_get_response_does_not_refresh_basic_auth() -> None:
    conn = RedfishConnection(
        base_url="https://bmc.example",
        username="root",
        password="pass",
        use_session_auth=False,
        verify_ssl=False,
    )
    session = MagicMock()
    session.get.return_value = _response(401)

    with patch.object(conn, "_ensure_session", return_value=session) as ensure_session:
        response = conn.get_response("/redfish/v1/Systems")

    assert response.status_code == 401
    ensure_session.assert_called_once()
    session.get.assert_called_once()


def test_get_response_does_not_refresh_other_status(session_conn: RedfishConnection) -> None:
    session = MagicMock()
    session.get.return_value = _response(404)

    with patch.object(session_conn, "_ensure_session", return_value=session) as ensure_session:
        response = session_conn.get_response("/redfish/v1/Systems")

    assert response.status_code == 404
    ensure_session.assert_called_once()
    session.get.assert_called_once()


def test_get_response_propagates_failed_relogin(session_conn: RedfishConnection) -> None:
    stale = MagicMock()
    stale.get.return_value = _response(401)

    def ensure_session() -> MagicMock:
        session = session_conn._session
        if not isinstance(session, MagicMock):
            raise RedfishConnectionError("Session login failed: 401 Unauthorized")
        return session

    session_conn._session = stale
    with patch.object(session_conn, "_ensure_session", side_effect=ensure_session):
        with pytest.raises(RedfishConnectionError, match="Session login failed"):
            session_conn.get_response("/redfish/v1/Systems")
