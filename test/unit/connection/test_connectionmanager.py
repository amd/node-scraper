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
from unittest.mock import MagicMock

from nodescraper.connection.inband.inbandmanager import InBandConnectionManager
from nodescraper.connection.inband.inbandremote import RemoteShell
from nodescraper.connection.inband.sshparams import SSHConnectionParams
from nodescraper.connection.oob_ssh.oob_ssh_connection_manager import (
    OobSshConnectionManager,
)
from nodescraper.connection.redfish.redfish_connection import RedfishConnection
from nodescraper.connection.redfish.redfish_manager import RedfishConnectionManager
from nodescraper.connection.redfish.redfish_params import RedfishConnectionParams
from nodescraper.connection.redfish.ssh_proxy_manager import (
    RedfishSshProxyConnectionManager,
)
from nodescraper.connection.redfish.ssh_proxy_params import (
    RedfishSshProxyConnectionParams,
)
from nodescraper.enums import ExecutionStatus, SystemLocation
from nodescraper.interfaces.connectionmanager import ConnectionManager
from nodescraper.models import SystemInfo, TaskResult


class DummyConnection:
    """Simple test connection class for testing ConnectionManager base behavior"""

    pass


class DummyConnectionManager(ConnectionManager[DummyConnection, None]):
    """Concrete implementation of ConnectionManager for testing base class behavior"""

    def connect(self) -> TaskResult:
        """Minimal connect implementation for testing"""
        self.connection = DummyConnection()
        return self.result


class TestConnectionManagerBase(unittest.TestCase):
    """Test suite for ConnectionManager base behavior"""

    def test_disconnect_clears_connection(self):
        """Test that disconnect clears the connection attribute"""
        system_info = SystemInfo(
            name="test_system",
            location=SystemLocation.LOCAL,
        )
        manager = DummyConnectionManager(system_info=system_info)
        manager.connection = DummyConnection()

        manager.disconnect()

        self.assertIsNone(manager.connection)

    def test_disconnect_resets_status(self):
        """Test that disconnect resets the result status to UNSET"""
        system_info = SystemInfo(
            name="test_system",
            location=SystemLocation.LOCAL,
        )
        manager = DummyConnectionManager(system_info=system_info)
        manager.connection = DummyConnection()
        manager.result.status = ExecutionStatus.OK

        manager.disconnect()

        self.assertEqual(manager.result.status, ExecutionStatus.UNSET)

    def test_context_manager_calls_disconnect(self):
        """Test that using connection manager as context manager calls disconnect on exit"""
        system_info = SystemInfo(
            name="test_system",
            location=SystemLocation.LOCAL,
        )
        manager = DummyConnectionManager(system_info=system_info)

        with manager:
            manager.connection = DummyConnection()
            self.assertIsNotNone(manager.connection)

        # After exiting context, disconnect should have been called
        self.assertIsNone(manager.connection)

    def test_connect_decorator_initializes_result(self):
        """Test that the connect decorator properly initializes the result"""
        system_info = SystemInfo(
            name="test_system",
            location=SystemLocation.LOCAL,
        )
        manager = DummyConnectionManager(system_info=system_info)

        result = manager.connect()

        self.assertIsNotNone(result)
        self.assertIsInstance(manager.connection, DummyConnection)

    def test_context_manager_handles_disconnect_exception(self):
        """BUG: __exit__ doesn't handle exceptions from disconnect()"""
        system_info = SystemInfo(
            name="test_system",
            location=SystemLocation.LOCAL,
        )
        manager = DummyConnectionManager(system_info=system_info)

        # Mock disconnect to raise an exception
        def bad_disconnect():
            raise RuntimeError("Disconnect failed")

        manager.disconnect = bad_disconnect

        # If disconnect raises an exception in __exit__, it could mask original exceptions
        with self.assertRaises(RuntimeError) as context:
            with manager:
                manager.connection = DummyConnection()

        self.assertIn("Disconnect failed", str(context.exception))


class TestInBandConnectionManagerDisconnect(unittest.TestCase):
    """Test suite specifically for InBandConnectionManager disconnect behavior"""

    def test_disconnect_remote_closes_ssh_client(self):
        """Test that disconnect properly closes SSH client for remote connections"""
        system_info = SystemInfo(
            name="test_system",
            location=SystemLocation.REMOTE,
        )
        manager = InBandConnectionManager(system_info=system_info)

        # Mock a RemoteShell with a client
        mock_client = MagicMock()
        mock_remote_shell = MagicMock(spec=RemoteShell)
        mock_remote_shell.client = mock_client

        manager.connection = mock_remote_shell

        manager.disconnect()

        # Verify client.close() was called
        mock_client.close.assert_called_once()
        # Verify connection was cleared by parent class
        self.assertIsNone(manager.connection)


class TestRedfishConnectionManagerDisconnect(unittest.TestCase):
    """Test suite for RedfishConnectionManager disconnect behavior"""

    def test_disconnect_closes_redfish_connection(self):
        """Test that disconnect properly closes Redfish connection"""
        system_info = SystemInfo(
            name="test_system",
            location=SystemLocation.REMOTE,
        )

        # Create manager without actual connection
        manager = RedfishConnectionManager(system_info=system_info)

        # Mock the connection with a close method
        mock_connection = MagicMock(spec=RedfishConnection)

        manager.connection = mock_connection

        manager.disconnect()

        # Verify connection.close() was called
        mock_connection.close.assert_called_once()
        # Verify connection was cleared by parent class
        self.assertIsNone(manager.connection)


class TestConnectionArgsModelClassVar(unittest.TestCase):
    """CONNECTION_ARGS_MODEL classvar drives dict -> model conversion of connection_args."""

    def setUp(self):
        self.system_info = SystemInfo(name="test_system", location=SystemLocation.REMOTE)

    def test_base_default_is_none(self):
        self.assertIsNone(ConnectionManager.CONNECTION_ARGS_MODEL)

    def test_subclasses_declare_expected_models(self):
        expected = {
            InBandConnectionManager: SSHConnectionParams,
            RedfishConnectionManager: RedfishConnectionParams,
            RedfishSshProxyConnectionManager: RedfishSshProxyConnectionParams,
            OobSshConnectionManager: RedfishConnectionParams,
        }
        for manager_cls, model in expected.items():
            with self.subTest(manager=manager_cls.__name__):
                self.assertIs(manager_cls.CONNECTION_ARGS_MODEL, model)

    def test_classvar_not_set_on_instance(self):
        manager = InBandConnectionManager(system_info=self.system_info)
        self.assertNotIn("CONNECTION_ARGS_MODEL", vars(manager))

    def test_dict_args_converted_to_model(self):
        manager = InBandConnectionManager(
            system_info=self.system_info,
            connection_args={"hostname": "host1", "username": "user1"},
        )
        self.assertIsInstance(manager.connection_args, SSHConnectionParams)
        self.assertEqual(manager.connection_args.hostname, "host1")
        self.assertEqual(manager.connection_args.username, "user1")

    def test_redfish_dict_args_converted_to_model(self):
        manager = RedfishConnectionManager(
            system_info=self.system_info,
            connection_args={"host": "bmc1", "username": "admin"},
        )
        self.assertIsInstance(manager.connection_args, RedfishConnectionParams)
        self.assertEqual(manager.connection_args.host, "bmc1")

    def test_oob_ssh_dict_args_converted_to_model(self):
        manager = OobSshConnectionManager(
            system_info=self.system_info,
            connection_args={"host": "bmc1", "username": "admin"},
        )
        self.assertIsInstance(manager.connection_args, RedfishConnectionParams)

    def test_ssh_proxy_dict_args_converted_to_model(self):
        manager = RedfishSshProxyConnectionManager(
            system_info=self.system_info,
            connection_args={"max_workers": 2},
        )
        self.assertIsInstance(manager.connection_args, RedfishSshProxyConnectionParams)
        self.assertEqual(manager.connection_args.max_workers, 2)

    def test_model_instance_passed_through_unchanged(self):
        params = SSHConnectionParams(hostname="host1", username="user1")
        manager = InBandConnectionManager(system_info=self.system_info, connection_args=params)
        self.assertIs(manager.connection_args, params)

    def test_none_args_stay_none(self):
        manager = InBandConnectionManager(system_info=self.system_info)
        self.assertIsNone(manager.connection_args)

    def test_dict_args_without_model_raises(self):
        with self.assertRaises(ValueError):
            DummyConnectionManager(system_info=self.system_info, connection_args={"a": 1})

    def test_custom_subclass_classvar_is_used(self):
        class CustomManager(ConnectionManager[DummyConnection, SSHConnectionParams]):
            CONNECTION_ARGS_MODEL = SSHConnectionParams

            def connect(self) -> TaskResult:
                return self.result

        manager = CustomManager(
            system_info=self.system_info,
            connection_args={"hostname": "h", "username": "u"},
        )
        self.assertIsInstance(manager.connection_args, SSHConnectionParams)

    def test_invalid_dict_args_raise_validation_error(self):
        with self.assertRaises(ValueError):
            InBandConnectionManager(system_info=self.system_info, connection_args={"port": 22})


if __name__ == "__main__":
    unittest.main()


class TestConnectionManagerAnnotations(unittest.TestCase):
    """Type annotations on the base connection manager must be resolvable."""

    def test_init_type_hints_are_resolvable(self):
        """get_type_hints must work on ConnectionManager.__init__ for introspection tooling"""
        import typing

        hints = typing.get_type_hints(ConnectionManager.__init__)

        self.assertIn("task_result_hooks", hints)
