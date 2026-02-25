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
from pathlib import Path

import pytest

from nodescraper.connection.inband.inband import CommandArtifact
from nodescraper.enums import ExecutionStatus, OSFamily
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.plugins.inband.rdma.rdma_collector import RdmaCollector
from nodescraper.plugins.inband.rdma.rdmadata import RdmaDataModel


@pytest.fixture
def collector(system_info, conn_mock):
    return RdmaCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


@pytest.fixture
def rdma_statistic_output():
    path = Path(__file__).parent / "fixtures" / "rdma_statistic_example_data.json"
    return path.read_text()


@pytest.fixture
def rdma_link_output():
    path = Path(__file__).parent / "fixtures" / "rdma_link_example_data.json"
    return path.read_text()


def test_collect_success(collector, conn_mock, rdma_link_output, rdma_statistic_output):
    """Successful collection returns RdmaDataModel with statistics and links (full fixtures)."""
    collector.system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.side_effect = [
        CommandArtifact(exit_code=0, stdout=rdma_link_output, stderr="", command="rdma link -j"),
        CommandArtifact(
            exit_code=0, stdout=rdma_statistic_output, stderr="", command="rdma statistic -j"
        ),
    ]
    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.OK
    assert data is not None
    assert isinstance(data, RdmaDataModel)
    # Full statistic fixture has 8 devices (bnxt_re0..bnxt_re7) with full stats
    assert len(data.statistic_list) == 8
    assert data.statistic_list[0].ifname == "bnxt_re0"
    # Full link fixture has 4 ionic links
    assert len(data.link_list) == 4
    assert data.link_list[0].ifname == "ionic_0"


def test_collect_both_commands_fail(collector, conn_mock):
    """When both rdma commands fail, status is EXECUTION_FAILURE and data is None."""
    collector.system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=1, stdout="", stderr="rdma command failed", command="rdma link -j"
    )
    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.EXECUTION_FAILURE
    assert data is None


def test_collect_empty_output(collector, conn_mock):
    """Empty JSON arrays yield empty lists in model."""
    collector.system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.side_effect = [
        CommandArtifact(exit_code=0, stdout="[]", stderr="", command="rdma link -j"),
        CommandArtifact(exit_code=0, stdout="[]", stderr="", command="rdma statistic -j"),
    ]
    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.OK
    assert data is not None
    assert data.link_list == []
    assert data.statistic_list == []
