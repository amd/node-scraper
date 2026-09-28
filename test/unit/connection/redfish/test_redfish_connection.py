# Copyright (C) 2025 Advanced Micro Devices, Inc.

from __future__ import annotations

from unittest.mock import patch

import pytest

from nodescraper.connection.redfish import RedfishConnection


@pytest.fixture
def rf_conn() -> RedfishConnection:
    return RedfishConnection(
        base_url="https://bmc.example",
        username="u",
        password=None,
        verify_ssl=False,
    )


@patch("nodescraper.connection.redfish.redfish_connection.requests.Session")
def test_close_clears_cached_session(mock_session_cls, rf_conn: RedfishConnection) -> None:
    """Baseline: close() drops the cached session so a later call builds a new one."""
    rf_conn._ensure_session()
    rf_conn.close()

    assert rf_conn._session is None


@patch("nodescraper.connection.redfish.redfish_connection.requests.Session")
def test_close_releases_underlying_http_session(
    mock_session_cls, rf_conn: RedfishConnection
) -> None:
    """close() must close the requests session so its connection pool is released."""
    session = rf_conn._ensure_session()
    rf_conn.close()

    session.close.assert_called_once()  # type: ignore
