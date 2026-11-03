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
import unittest
from unittest.mock import MagicMock, patch

from nodescraper.connection.oob_rest import (
    OobRestConnection,
    OobRestConnectionManager,
    OobRestConnectionParams,
)
from nodescraper.enums import ExecutionStatus, SystemLocation
from nodescraper.models import SystemInfo


def _system_info() -> SystemInfo:
    return SystemInfo(name="test_system", location=SystemLocation.LOCAL)


class TestOobRestConnectionManager(unittest.TestCase):
    """Test suite for OobRestConnectionManager."""

    def test_connect_without_args_fails(self):
        """connect() with no connection_args reports EXECUTION_FAILURE."""
        manager = OobRestConnectionManager(system_info=_system_info())
        result = manager.connect()
        self.assertEqual(result.status, ExecutionStatus.EXECUTION_FAILURE)
        self.assertIsNone(manager.connection)

    @patch("nodescraper.connection.oob_rest.oob_rest_connection.requests.Session")
    def test_connect_with_dict_args_authenticates(self, mock_session_cls):
        """A dict connection_args is coerced to params and connect() authenticates."""
        session = MagicMock()
        mock_session_cls.return_value = session
        manager = OobRestConnectionManager(
            system_info=_system_info(),
            connection_args={
                "host": "10.0.0.1",
                "username": "admin",
                "password": "secret",
                "login_payload_extra": {"tenant": "default"},
            },
        )
        result = manager.connect()
        self.assertEqual(result.status, ExecutionStatus.OK)
        self.assertIsInstance(manager.connection, OobRestConnection)

        # Login POST issued once, to the configured path, with the extra payload merged in.
        session.post.assert_called_once()
        call = session.post.call_args
        self.assertEqual(call.args[0], "https://10.0.0.1/v1/login")
        self.assertEqual(call.kwargs["json"]["tenant"], "default")
        self.assertEqual(call.kwargs["json"]["username"], "admin")
        self.assertEqual(call.kwargs["json"]["password"], "secret")

    @patch("nodescraper.connection.oob_rest.oob_rest_connection.requests.Session")
    def test_connect_with_params_instance(self, mock_session_cls):
        """connect() accepts an OobRestConnectionParams instance directly."""
        mock_session_cls.return_value = MagicMock()
        params = OobRestConnectionParams(host="10.0.0.2", username="admin", password="pw")
        manager = OobRestConnectionManager(system_info=_system_info(), connection_args=params)
        result = manager.connect()
        self.assertEqual(result.status, ExecutionStatus.OK)
        self.assertIsInstance(manager.connection, OobRestConnection)

    @patch("nodescraper.connection.oob_rest.oob_rest_connection.requests.Session")
    def test_connect_auth_failure_reports_failure(self, mock_session_cls):
        """An auth exception surfaces as EXECUTION_FAILURE and leaves no connection."""
        session = MagicMock()
        session.post.side_effect = Exception("401 unauthorized")
        mock_session_cls.return_value = session
        manager = OobRestConnectionManager(
            system_info=_system_info(),
            connection_args={"host": "10.0.0.3", "username": "admin", "password": "pw"},
        )
        result = manager.connect()
        self.assertEqual(result.status, ExecutionStatus.EXECUTION_FAILURE)
        self.assertIsNone(manager.connection)

    @patch("nodescraper.connection.oob_rest.oob_rest_connection.requests.Session")
    def test_disconnect_closes_and_clears(self, mock_session_cls):
        """disconnect() closes the session and clears the connection."""
        session = MagicMock()
        mock_session_cls.return_value = session
        manager = OobRestConnectionManager(
            system_info=_system_info(),
            connection_args={"host": "10.0.0.4", "username": "admin", "password": "pw"},
        )
        manager.connect()
        manager.disconnect()
        session.close.assert_called_once()
        self.assertIsNone(manager.connection)


if __name__ == "__main__":
    unittest.main()
