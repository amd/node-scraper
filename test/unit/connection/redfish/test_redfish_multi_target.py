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
import logging
from typing import cast
from unittest.mock import MagicMock, patch

from nodescraper.base import OOBandDataPlugin, RedfishDataCollector
from nodescraper.connection.oob_ssh.oob_ssh_connection_manager import (
    OobSshConnectionManager,
)
from nodescraper.connection.redfish import (
    MultiTargetRedfishConnection,
    RedfishConnection,
    RedfishConnectionError,
    RedfishConnectionManager,
    RedfishConnectionParams,
)
from nodescraper.enums import ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import DataModel, SystemInfo


class SampleModel(DataModel):
    label: str = ""


class SampleCollector(RedfishDataCollector[SampleModel, None]):
    DATA_MODEL = SampleModel

    def collect_data(self, args=None):
        """Collect a label from the fake connection.

        Args:
            args: Unused collection arguments.

        Returns:
            tuple[TaskResult, Optional[SampleModel]]: Collector result and data model.
        """
        marker = getattr(self.connection, "marker", "")
        if marker == "boom":
            raise RuntimeError("bmc down")
        self.result.status = ExecutionStatus.OK
        self.result.message = marker
        return self.result, SampleModel(label=marker)


class SampleAnalyzer(DataAnalyzer[SampleModel, None]):
    DATA_MODEL = SampleModel

    def analyze_data(self, data, args=None):
        """Flag a bad label as an analysis error.

        Args:
            data: Collected sample model.
            args: Unused analysis arguments.

        Returns:
            TaskResult: Analysis result for this target.
        """
        if data.label == "bad":
            self.result.status = ExecutionStatus.ERROR
            self.result.message = "check failed"
        else:
            self.result.status = ExecutionStatus.OK
            self.result.message = "ok"
        return self.result


class SamplePlugin(OOBandDataPlugin[SampleModel, None, None]):
    DATA_MODEL = SampleModel
    COLLECTOR = SampleCollector
    ANALYZER = SampleAnalyzer


def _manager(
    system_info: SystemInfo, targets: list[RedfishConnectionParams], **extra
) -> RedfishConnectionManager:
    return RedfishConnectionManager(
        system_info=system_info,
        connection_args=RedfishConnectionParams(targets=targets, **extra),
    )


@patch("nodescraper.connection.redfish.redfish_manager.RedfishConnection")
def test_partial_connect_keeps_reachable_bmc(mock_conn_cls, system_info: SystemInfo) -> None:
    """One unreachable BMC leaves the reachable BMC connected at warning."""

    def build(**kwargs):
        conn = MagicMock()
        if "down" in kwargs["base_url"]:
            conn._ensure_session.side_effect = RedfishConnectionError("unreachable")
        return conn

    mock_conn_cls.side_effect = build
    manager = _manager(
        system_info,
        [
            RedfishConnectionParams(target_key="good", host="bmc-good.example", username="admin"),
            RedfishConnectionParams(target_key="bad", host="bmc-down.example", username="admin"),
        ],
        max_workers=2,
    )

    result = manager.connect()

    assert result.status == ExecutionStatus.WARNING
    assert isinstance(manager.connection, MultiTargetRedfishConnection)
    assert set(manager.connection.target_connections) == {"good"}
    assert "bad" in manager.connection.failed_targets
    assert manager.connection.max_workers == 2


@patch("nodescraper.connection.redfish.redfish_manager.RedfishConnection")
def test_every_target_down_fails_connect(mock_conn_cls, system_info: SystemInfo) -> None:
    """Every target failing is an execution failure and does not set a connection."""
    mock_conn_cls.side_effect = lambda **kwargs: MagicMock(
        _ensure_session=MagicMock(side_effect=RedfishConnectionError("unreachable"))
    )
    manager = _manager(
        system_info,
        [
            RedfishConnectionParams(target_key="a", host="bmc-a.example", username="admin"),
            RedfishConnectionParams(target_key="b", host="bmc-b.example", username="admin"),
        ],
    )

    result = manager.connect()

    assert result.status == ExecutionStatus.EXECUTION_FAILURE
    assert manager.connection is None


def test_one_bmc_collection_failure_stays_warning(system_info: SystemInfo) -> None:
    """A collect failure and a missed connect stay a warning when another target succeeds."""
    good = MagicMock()
    good.marker = "good"
    bad = MagicMock()
    bad.marker = "boom"
    multi = MultiTargetRedfishConnection(
        {"good": good, "bad": bad},
        max_workers=2,
        failed_targets={"offline": "Redfish connection failed for target 'offline'"},
    )
    collector = SampleCollector(
        system_info=system_info,
        connection=cast(RedfishConnection, multi),
        logger=logging.getLogger("multi-target-test"),
        parent="SamplePlugin",
    )

    result, data = collector.collect_data()

    assert data is None
    assert result.status == ExecutionStatus.WARNING
    assert result.status <= ExecutionStatus.WARNING
    assert multi.multi_target_data["good"].label == "good"
    assert "bad" not in multi.multi_target_data
    assert "offline" in result.message


def test_analyze_reads_data_before_disconnect(system_info: SystemInfo) -> None:
    """Analysis uses data still held on the open multi-target connection."""
    multi = MultiTargetRedfishConnection({"good": MagicMock()})
    multi.multi_target_data["good"] = SampleModel(label="good")
    connection_manager = MagicMock()
    connection_manager.connection = multi
    connection_manager._multi_target_data = {}
    plugin = SamplePlugin(
        system_info=system_info,
        logger=logging.getLogger("multi-target-test"),
        connection_manager=connection_manager,
    )

    result = plugin.analyze()

    assert result.status == ExecutionStatus.OK


def test_analyze_error_on_collected_data_fails(system_info: SystemInfo) -> None:
    """A check failure on data that was collected still fails analysis."""
    multi = MultiTargetRedfishConnection({"bad": MagicMock(), "good": MagicMock()})
    multi.multi_target_data["bad"] = SampleModel(label="bad")
    multi.multi_target_data["good"] = SampleModel(label="good")
    connection_manager = MagicMock()
    connection_manager.connection = multi
    plugin = SamplePlugin(
        system_info=system_info,
        logger=logging.getLogger("multi-target-test"),
        connection_manager=connection_manager,
    )

    result = plugin.analyze()

    assert result.status == ExecutionStatus.ERROR


def test_oob_ssh_skips_targets_without_a_single_host(system_info: SystemInfo) -> None:
    """OOB SSH does not fan out across a Redfish targets list."""
    manager = OobSshConnectionManager(
        system_info=system_info,
        connection_args=RedfishConnectionParams(
            targets=[
                RedfishConnectionParams(host="bmc-a.example", username="admin"),
                RedfishConnectionParams(host="bmc-b.example", username="admin"),
            ]
        ),
    )

    result = manager.connect()

    assert result.status == ExecutionStatus.NOT_RAN
    assert manager.connection is None


@patch("nodescraper.connection.oob_ssh.oob_ssh_connection_manager.RemoteShell")
def test_oob_ssh_uses_top_level_host_beside_targets(mock_shell, system_info: SystemInfo) -> None:
    """A top-level host keeps OOB SSH on one BMC while Redfish uses targets."""
    mock_shell.return_value = MagicMock()
    manager = OobSshConnectionManager(
        system_info=system_info,
        connection_args=RedfishConnectionParams(
            host="bmc-ssh.example",
            username="admin",
            targets=[
                RedfishConnectionParams(host="bmc-a.example", username="admin"),
                RedfishConnectionParams(host="bmc-b.example", username="admin"),
            ],
        ),
    )

    result = manager.connect()

    assert result.status == ExecutionStatus.OK
    assert mock_shell.call_args.args[0].hostname == "bmc-ssh.example"
