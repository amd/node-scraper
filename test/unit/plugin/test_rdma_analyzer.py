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

from nodescraper.enums import EventPriority, ExecutionStatus
from nodescraper.plugins.inband.rdma.rdma_analyzer import RdmaAnalyzer
from nodescraper.plugins.inband.rdma.rdmadata import (
    RdmaDataModel,
    RdmaLink,
    RdmaStatistics,
)


@pytest.fixture
def rdma_analyzer(system_info):
    return RdmaAnalyzer(system_info)


@pytest.fixture
def plugin_fixtures_path():
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def clean_rdma_model(plugin_fixtures_path):
    """RDMA data with no errors (all counters zero)."""
    path = plugin_fixtures_path / "rdma_statistic_example_data.json"
    data = json.loads(path.read_text())
    stats = [RdmaStatistics(**s) for s in data]
    return RdmaDataModel(statistic_list=stats)


@pytest.fixture
def clean_stats(plugin_fixtures_path):
    """List of clean RdmaStatistics (no errors) for building models with links."""
    path = plugin_fixtures_path / "rdma_statistic_example_data.json"
    data = json.loads(path.read_text())
    return [RdmaStatistics(**s) for s in data]


def test_no_errors_detected(rdma_analyzer, clean_rdma_model):
    """Test with nominal data that has no errors."""
    result = rdma_analyzer.analyze_data(clean_rdma_model)
    assert result.status == ExecutionStatus.OK
    assert len(result.events) == 0


def test_single_error_detected(rdma_analyzer, clean_rdma_model):
    """Test with data containing a single error."""
    stats = list(clean_rdma_model.statistic_list)
    stats[0].tx_roce_errors = 5
    model = RdmaDataModel(statistic_list=stats)
    result = rdma_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.ERROR
    assert "RDMA errors detected in statistics" in result.message
    assert len(result.events) == 1
    assert result.events[0].description == "RDMA error detected on bnxt_re0: [tx_roce_errors]"
    assert result.events[0].priority == EventPriority.ERROR
    assert result.events[0].data["errors"] == {"tx_roce_errors": 5}
    assert result.events[0].data["interface"] == "bnxt_re0"


def test_multiple_errors_detected(rdma_analyzer, clean_rdma_model):
    """Test with data containing multiple errors (grouped per interface)."""
    stats = list(clean_rdma_model.statistic_list)
    stats[0].tx_roce_errors = 10
    stats[0].rx_roce_errors = 3
    stats[1].packet_seq_err = 7
    model = RdmaDataModel(statistic_list=stats)
    result = rdma_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.ERROR
    assert "RDMA errors detected in statistics" in result.message
    assert len(result.events) == 2  # one per interface
    for event in result.events:
        assert event.priority == EventPriority.ERROR
    # Total 3 errors across 2 interfaces
    assert sum(len(e.data["errors"]) for e in result.events) == 3


def test_critical_error_detected(rdma_analyzer, clean_rdma_model):
    """Test with data containing a critical error (grouped per interface)."""
    stats = list(clean_rdma_model.statistic_list)
    stats[0].unrecoverable_err = 1
    stats[0].res_tx_pci_err = 2
    model = RdmaDataModel(statistic_list=stats)
    result = rdma_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.ERROR
    assert "RDMA errors detected in statistics" in result.message
    assert len(result.events) == 1  # one event per interface
    assert result.events[0].priority == EventPriority.CRITICAL
    assert "unrecoverable_err" in result.events[0].data["errors"]
    assert "res_tx_pci_err" in result.events[0].data["errors"]


def test_empty_statistics(rdma_analyzer):
    """Test with empty statistics list."""
    model = RdmaDataModel(statistic_list=[], link_list=[])
    result = rdma_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.NOT_RAN
    assert result.message == "RDMA statistics list is empty"


def test_multiple_interfaces_with_errors(rdma_analyzer, clean_rdma_model):
    """Test with errors across multiple interfaces."""
    stats = list(clean_rdma_model.statistic_list)
    stats[0].max_retry_exceeded = 15
    stats[2].local_ack_timeout_err = 8
    stats[4].out_of_buffer = 100
    model = RdmaDataModel(statistic_list=stats)
    result = rdma_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.ERROR
    assert len(result.events) == 3
    interfaces = {event.data["interface"] for event in result.events}
    assert len(interfaces) == 3


def test_all_error_types(rdma_analyzer):
    """Test that all error fields are properly detected (grouped in one event)."""
    stats = RdmaStatistics(
        ifname="bnxt_re_test",
        port=1,
        recoverable_errors=1,
        tx_roce_errors=1,
        unrecoverable_err=1,
    )
    model = RdmaDataModel(statistic_list=[stats])
    result = rdma_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.ERROR
    assert len(result.events) == 1  # one event per interface
    assert "unrecoverable_err" in result.events[0].data["errors"]
    assert result.events[0].priority == EventPriority.CRITICAL
    assert set(result.events[0].data["errors"].keys()) == {
        "recoverable_errors",
        "tx_roce_errors",
        "unrecoverable_err",
    }


def test_zero_errors_are_ignored(rdma_analyzer):
    """Test that zero-value errors are not reported."""
    stats = RdmaStatistics(
        ifname="bnxt_re_test",
        port=1,
        tx_roce_errors=0,
        rx_roce_errors=0,
        unrecoverable_err=0,
    )
    model = RdmaDataModel(statistic_list=[stats])
    result = rdma_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.OK
    assert len(result.events) == 0


def test_rdma_link_all_active(rdma_analyzer, clean_stats):
    """Test with RDMA links that are all active and up."""
    links = [
        RdmaLink(
            ifindex=0,
            ifname="ionic_0",
            port=1,
            state="ACTIVE",
            physical_state="LINK_UP",
            netdev="benic0p1",
            netdev_index=3,
        ),
        RdmaLink(
            ifindex=1,
            ifname="ionic_1",
            port=1,
            state="ACTIVE",
            physical_state="LINK_UP",
            netdev="benic1p1",
            netdev_index=4,
        ),
    ]
    model = RdmaDataModel(statistic_list=clean_stats, link_list=links)
    result = rdma_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.OK
    assert result.message == "No RDMA errors detected in statistics"
    assert len(result.events) == 0


def test_rdma_link_down_detected(rdma_analyzer, clean_stats):
    """Test with RDMA links that are down"""
    links = [
        RdmaLink(
            ifindex=0,
            ifname="ionic_0",
            port=1,
            state="ACTIVE",
            physical_state="LINK_UP",
            netdev="benic0p1",
            netdev_index=3,
        ),
        RdmaLink(
            ifindex=1,
            ifname="ionic_1",
            port=1,
            state="DOWN",
            physical_state="LINK_DOWN",
            netdev="benic1p1",
            netdev_index=4,
        ),
    ]
    model = RdmaDataModel(statistic_list=clean_stats, link_list=links)
    result = rdma_analyzer.analyze_data(model)
    # Current implementation only checks statistics, not link state
    assert result.status == ExecutionStatus.OK


def test_rdma_link_empty_list(rdma_analyzer, clean_stats):
    """Test with empty RDMA link list."""
    model = RdmaDataModel(statistic_list=clean_stats, link_list=[])
    result = rdma_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.OK
    assert result.message == "No RDMA errors detected in statistics"


def test_rdma_link_multiple_interfaces(rdma_analyzer, clean_stats):
    """Test with multiple RDMA interfaces with different link states."""
    links = [
        RdmaLink(
            ifindex=0,
            ifname="ionic_0",
            port=1,
            state="ACTIVE",
            physical_state="LINK_UP",
            netdev="benic0p1",
            netdev_index=3,
        ),
        RdmaLink(
            ifindex=1,
            ifname="ionic_1",
            port=1,
            state="ACTIVE",
            physical_state="LINK_UP",
            netdev="benic1p1",
            netdev_index=4,
        ),
        RdmaLink(
            ifindex=2,
            ifname="ionic_2",
            port=1,
            state="ACTIVE",
            physical_state="LINK_UP",
            netdev="benic2p1",
            netdev_index=5,
        ),
    ]
    model = RdmaDataModel(statistic_list=clean_stats, link_list=links)
    result = rdma_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.OK
    assert len(result.events) == 0
