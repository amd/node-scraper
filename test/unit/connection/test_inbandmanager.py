###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
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

from nodescraper.connection.inband.inbandlocal import LocalShell
from nodescraper.connection.inband.inbandmanager import InBandConnectionManager
from nodescraper.connection.inband.inbandremote import RemoteShell, SSHConnectionError
from nodescraper.connection.inband.sshparams import SSHConnectionParams
from nodescraper.enums import SystemLocation
from nodescraper.models import SystemInfo


class TestInBandConnectionManager(unittest.TestCase):
    """Test suite for InBandConnectionManager"""

    def setUp(self):
        """Set up test fixtures"""
        self.system_info = SystemInfo(
            name="test_system",
            location=SystemLocation.REMOTE,
        )

    def test_connect_local(self):
        """Test connecting to a local system"""
        from nodescraper.enums import ExecutionStatus

        local_system_info = SystemInfo(
            name="local_system",
            location=SystemLocation.LOCAL,
        )
        manager = InBandConnectionManager(system_info=local_system_info)

        result = manager.connect()

        self.assertIsInstance(manager.connection, LocalShell)
        self.assertIn(result.status, [ExecutionStatus.OK, ExecutionStatus.UNSET])

    @patch("nodescraper.connection.inband.inbandmanager.RemoteShell")
    def test_connect_remote_success(self, mock_remote_shell_class):
        """Test successful remote SSH connection"""
        mock_remote_shell = MagicMock(spec=RemoteShell)
        mock_remote_shell_class.return_value = mock_remote_shell

        ssh_params = SSHConnectionParams(
            hostname="test.example.com", username="testuser", password="testpass"
        )

        manager = InBandConnectionManager(system_info=self.system_info, connection_args=ssh_params)

        _result = manager.connect()

        mock_remote_shell_class.assert_called_once_with(ssh_params)
        mock_remote_shell.connect_ssh.assert_called_once()
        self.assertEqual(manager.connection, mock_remote_shell)

    def test_connect_remote_no_credentials(self):
        """Test remote connection without SSH credentials"""
        from nodescraper.enums import ExecutionStatus

        manager = InBandConnectionManager(system_info=self.system_info)

        result = manager.connect()

        self.assertEqual(result.status, ExecutionStatus.EXECUTION_FAILURE)

    def test_disconnect_remote_calls_client_close(self):
        """Test that disconnect calls client.close() for remote connections"""
        mock_client = MagicMock()
        mock_remote_shell = MagicMock(spec=RemoteShell)
        mock_remote_shell.client = mock_client

        manager = InBandConnectionManager(system_info=self.system_info)
        manager.connection = mock_remote_shell

        manager.disconnect()

        mock_client.close.assert_called_once()

    def test_disconnect_local_does_not_call_client_close(self):
        """Test that disconnect does not call client.close() for local connections"""
        mock_local_shell = MagicMock(spec=LocalShell)

        manager = InBandConnectionManager(system_info=self.system_info)
        manager.connection = mock_local_shell

        # Should not raise an error even though LocalShell doesn't have a client attribute
        manager.disconnect()

        # Verify that we didn't try to access client.close()
        self.assertFalse(hasattr(mock_local_shell, "client"))

    def test_disconnect_remote_with_none_client_raises_error(self):
        """BUG: disconnect fails when RemoteShell.client is None"""
        mock_remote_shell = MagicMock(spec=RemoteShell)
        mock_remote_shell.client = None

        manager = InBandConnectionManager(system_info=self.system_info)
        manager.connection = mock_remote_shell

        # This should raise AttributeError because client is None
        with self.assertRaises(AttributeError):
            manager.disconnect()

    def test_disconnect_remote_when_client_close_raises_exception(self):
        """BUG: if client.close() raises exception, super().disconnect() is never called"""
        mock_client = MagicMock()
        mock_client.close.side_effect = Exception("Connection already closed")

        mock_remote_shell = MagicMock(spec=RemoteShell)
        mock_remote_shell.client = mock_client

        manager = InBandConnectionManager(system_info=self.system_info)
        manager.connection = mock_remote_shell

        # This should raise the exception from close()
        with self.assertRaises(Exception) as context:
            manager.disconnect()

        self.assertIn("Connection already closed", str(context.exception))

        # BUG: Connection is not cleared because super().disconnect() was never called
        self.assertIsNotNone(manager.connection)

    @patch("nodescraper.connection.inband.inbandmanager.RemoteShell")
    def test_connect_remote_failure_clears_connection(self, mock_remote_shell_class):
        """A failed SSH connect must not leave an unusable connection object behind"""
        mock_remote_shell = MagicMock(spec=RemoteShell)
        mock_remote_shell.connect_ssh.side_effect = SSHConnectionError("SSH Authentication failed")
        mock_remote_shell_class.return_value = mock_remote_shell

        manager = InBandConnectionManager(
            system_info=self.system_info,
            connection_args=SSHConnectionParams(
                hostname="test.example.com",
                username="testuser",
                password="testpass",
            ),
        )

        manager.connect()

        self.assertIsNone(manager.connection)


if __name__ == "__main__":
    unittest.main()
