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
import json
from pathlib import Path

import pytest

from nodescraper.connection.inband.inband import CommandArtifact
from nodescraper.enums import EventPriority, ExecutionStatus, OSFamily
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
        CommandArtifact(exit_code=0, stdout="", stderr="", command="rdma dev"),
        CommandArtifact(exit_code=0, stdout="", stderr="", command="rdma link"),
    ]
    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.OK
    assert data is not None
    assert isinstance(data, RdmaDataModel)
    assert len(data.statistic_list) == 12
    assert data.statistic_list[0].ifname == "ionic_0"
    assert data.statistic_list[0].vendor_statistics is not None
    assert data.statistic_list[0].vendor_statistics.tx_rdma_ucast_bytes == 0
    # Full link fixture has 4 ionic links
    assert len(data.link_list) == 4
    assert data.link_list[0].ifname == "ionic_0"


def test_collect_both_commands_fail(collector, conn_mock):
    """When all rdma commands fail, status is EXECUTION_FAILURE and data is None."""
    collector.system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=1, stdout="", stderr="rdma command failed", command="rdma link -j"
    )
    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.EXECUTION_FAILURE
    assert data is None


def test_collect_empty_output(collector, conn_mock):
    """No RDMA devices: WARNING, message 'No RDMA devices found', no data so analyzer is skipped."""
    collector.system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.side_effect = [
        CommandArtifact(exit_code=0, stdout="[]", stderr="", command="rdma link -j"),
        CommandArtifact(exit_code=0, stdout="[]", stderr="", command="rdma statistic -j"),
        CommandArtifact(exit_code=0, stdout="", stderr="", command="rdma dev"),
        CommandArtifact(exit_code=0, stdout="", stderr="", command="rdma link"),
    ]
    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.WARNING
    assert res.message == "No RDMA devices found"
    assert data is None


# Sample text output for rdma dev / rdma link (non-JSON)
RDMA_DEV_OUTPUT = """0: abcdef25s0: node_type ca fw 1.117.1-a-63 node_guid 1234:56ff:890f:1111 sys_image_guid 1234:56ff:890f:1111
1: abcdef105s0: node_type ca fw 1.117.1-a-63 node_guid 2222:81ff:3333:b450 sys_image_guid 2222:81ff:3333:b450"""

RDMA_LINK_OUTPUT = """link rocep9s0/1 state DOWN physical_state POLLING netdev benic8p1
link abcdef25s0/1 state DOWN physical_state POLLING netdev mock7p1
"""


def test_parse_rdma_dev_roce(collector):
    """Test parsing rdma dev output with RoCE devices."""
    devices = collector._parse_rdma_dev(RDMA_DEV_OUTPUT)
    assert len(devices) == 2
    device1 = devices[0]
    assert device1.device == "abcdef25s0"
    assert device1.node_type == "ca"
    assert device1.attributes["fw_version"] == "1.117.1-a-63"
    assert device1.node_guid == "1234:56ff:890f:1111"
    assert device1.sys_image_guid == "1234:56ff:890f:1111"
    device2 = devices[1]
    assert device2.device == "abcdef105s0"
    assert device2.node_type == "ca"
    assert device2.node_guid == "2222:81ff:3333:b450"


def test_parse_rdma_dev_empty(collector):
    """Test parsing empty rdma dev output."""
    devices = collector._parse_rdma_dev("")
    assert len(devices) == 0


def test_parse_rdma_link_text_roce(collector):
    """Test parsing rdma link (text) output with RoCE devices."""
    links = collector._parse_rdma_link_text(RDMA_LINK_OUTPUT)
    assert len(links) == 2
    link1 = next((link for link in links if link.device == "rocep9s0"), None)
    assert link1 is not None
    assert link1.port == 1
    assert link1.state == "DOWN"
    assert link1.physical_state == "POLLING"
    assert link1.netdev == "benic8p1"
    link2 = next((link for link in links if link.device == "abcdef25s0"), None)
    assert link2 is not None
    assert link2.netdev == "mock7p1"


def test_parse_rdma_link_text_empty(collector):
    """Test parsing empty rdma link (text) output."""
    links = collector._parse_rdma_link_text("")
    assert len(links) == 0


def test_collect_extra_fields_warning(collector, conn_mock):
    """Extra keys in a statistic row produce a warning event but collection succeeds."""
    collector.system_info.os_family = OSFamily.LINUX
    stat_data = [
        {
            "ifname": "ionic_0",
            "port": 1,
            "tx_rdma_ucast_bytes": 0,
            "unknown_field_1": 42,
            "unknown_field_2": 99,
        }
    ]
    conn_mock.run_command.side_effect = [
        CommandArtifact(exit_code=0, stdout="[]", stderr="", command="rdma link -j"),
        CommandArtifact(
            exit_code=0,
            stdout=json.dumps(stat_data),
            stderr="",
            command="rdma statistic -j",
        ),
        CommandArtifact(exit_code=0, stdout="", stderr="", command="rdma dev"),
        CommandArtifact(exit_code=0, stdout="", stderr="", command="rdma link"),
    ]
    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.OK
    assert data is not None
    assert len(data.statistic_list) == 1
    assert data.statistic_list[0].vendor_statistics is not None
    extra_events = [e for e in res.events if "Unexpected fields" in e.description]
    assert len(extra_events) == 1
    assert extra_events[0].priority == EventPriority.WARNING
    assert "unknown_field_1" in extra_events[0].data["extra_fields"]
    assert "unknown_field_2" in extra_events[0].data["extra_fields"]


def test_collect_missing_fields_warning(collector, conn_mock):
    """Missing vendor fields produce a warning event."""
    collector.system_info.os_family = OSFamily.LINUX
    stat_data = [{"ifname": "ionic_0", "port": 1, "tx_rdma_ucast_bytes": 0}]
    conn_mock.run_command.side_effect = [
        CommandArtifact(exit_code=0, stdout="[]", stderr="", command="rdma link -j"),
        CommandArtifact(
            exit_code=0,
            stdout=json.dumps(stat_data),
            stderr="",
            command="rdma statistic -j",
        ),
        CommandArtifact(exit_code=0, stdout="", stderr="", command="rdma dev"),
        CommandArtifact(exit_code=0, stdout="", stderr="", command="rdma link"),
    ]
    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.OK
    assert data is not None
    assert len(data.statistic_list) == 1
    missing_events = [e for e in res.events if "Missing fields" in e.description]
    assert len(missing_events) == 1
    assert missing_events[0].priority == EventPriority.WARNING
    assert "tx_rdma_ucast_pkts" in missing_events[0].data["missing_fields"]


def test_collect_extra_and_missing_fields_warning(collector, conn_mock):
    """Both extra and unknown vendor keys produce separate warnings (mlx)."""
    collector.system_info.os_family = OSFamily.LINUX
    stat_data = [
        {
            "ifname": "mlx5_0",
            "port": 1,
            "rx_write_requests": 0,
            "brand_new_counter": 7,
        }
    ]
    conn_mock.run_command.side_effect = [
        CommandArtifact(exit_code=0, stdout="[]", stderr="", command="rdma link -j"),
        CommandArtifact(
            exit_code=0,
            stdout=json.dumps(stat_data),
            stderr="",
            command="rdma statistic -j",
        ),
        CommandArtifact(exit_code=0, stdout="", stderr="", command="rdma dev"),
        CommandArtifact(exit_code=0, stdout="", stderr="", command="rdma link"),
    ]
    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.OK
    assert data is not None
    extra_events = [e for e in res.events if "Unexpected fields" in e.description]
    missing_events = [e for e in res.events if "Missing fields" in e.description]
    assert len(extra_events) == 1
    assert len(missing_events) == 1
    assert "brand_new_counter" in extra_events[0].data["extra_fields"]
    assert "rx_read_requests" in missing_events[0].data["missing_fields"]


def test_collect_no_field_warnings_when_fixture_matches(
    collector, conn_mock, rdma_statistic_output
):
    """Full fixture rows match vendor models: no missing/extra field warnings."""
    collector.system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.side_effect = [
        CommandArtifact(exit_code=0, stdout="[]", stderr="", command="rdma link -j"),
        CommandArtifact(
            exit_code=0,
            stdout=rdma_statistic_output,
            stderr="",
            command="rdma statistic -j",
        ),
        CommandArtifact(exit_code=0, stdout="", stderr="", command="rdma dev"),
        CommandArtifact(exit_code=0, stdout="", stderr="", command="rdma link"),
    ]
    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.OK
    assert data is not None
    drift = [
        e
        for e in res.events
        if "Unexpected fields" in e.description or "Missing fields" in e.description
    ]
    assert drift == []
