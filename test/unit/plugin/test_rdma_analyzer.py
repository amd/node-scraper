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
from typing import Optional

import pytest

from nodescraper.enums import EventPriority, ExecutionStatus
from nodescraper.plugins.inband.rdma.analyzer_args import RdmaAnalyzerArgs
from nodescraper.plugins.inband.rdma.rdma_analyzer import RdmaAnalyzer
from nodescraper.plugins.inband.rdma.rdmadata import (
    VENDOR_PREFIX_MAP,
    Cx7RdmaStatistics,
    PollaraRdmaStatistics,
    RdmaDataModel,
    RdmaLink,
    RdmaStatistics,
    RdmaVendorStatistics,
    Thor2RdmaStatistics,
)


@pytest.fixture
def rdma_analyzer(system_info):
    return RdmaAnalyzer(system_info)


@pytest.fixture
def plugin_fixtures_path():
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def example_stat_dicts(plugin_fixtures_path):
    path = plugin_fixtures_path / "rdma_statistic_example_data.json"
    return json.loads(path.read_text())


def _build_stats(data: list[dict]) -> list[RdmaStatistics]:
    """Build RdmaStatistics list from raw dicts using vendor prefix map."""
    stats = []
    for entry in data:
        ifname = entry.get("ifname", "")
        vendor_stats: Optional[RdmaVendorStatistics] = None
        for prefix, vendor_cls in VENDOR_PREFIX_MAP.items():
            if ifname.startswith(prefix):
                vendor_stats = vendor_cls(**entry)
                break
        stats.append(
            RdmaStatistics(
                ifname=entry.get("ifname"),
                port=entry.get("port"),
                vendor_statistics=vendor_stats,
            )
        )
    return stats


@pytest.fixture
def clean_rdma_model(example_stat_dicts):
    return RdmaDataModel(statistic_list=_build_stats(example_stat_dicts))


@pytest.fixture
def clean_stats(example_stat_dicts):
    return _build_stats(example_stat_dicts)


def test_no_errors_detected(rdma_analyzer, clean_rdma_model):
    result = rdma_analyzer.analyze_data(clean_rdma_model)
    assert result.status == ExecutionStatus.OK
    assert len(result.events) == 0


def test_single_error_detected(rdma_analyzer, example_stat_dicts):
    stats_with_error = _build_stats(example_stat_dicts)
    stats_with_error[0].vendor_statistics.req_rx_pkt_seq_err = 5
    model = RdmaDataModel(statistic_list=stats_with_error)
    result = rdma_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.ERROR
    assert "RDMA errors detected in statistics" in result.message
    assert len(result.events) == 1
    assert result.events[0].description == "RDMA error detected"
    assert result.events[0].priority == EventPriority.ERROR
    assert result.events[0].data["errors"]["req_rx_pkt_seq_err"] == 5
    assert result.events[0].data["interface"] == "ionic_0"


def test_multiple_errors_detected(rdma_analyzer, example_stat_dicts):
    stats_with_errors = _build_stats(example_stat_dicts)
    stats_with_errors[0].vendor_statistics.req_rx_rmt_acc_err = 10
    stats_with_errors[0].vendor_statistics.req_tx_loc_oper_err = 3
    stats_with_errors[8].vendor_statistics.packet_seq_err = 7
    model = RdmaDataModel(statistic_list=stats_with_errors)
    result = rdma_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.ERROR
    assert "RDMA errors detected in statistics" in result.message
    # Errors on the same interface are aggregated into a single event:
    # ionic_0 (2 counters) + mlx5_0 (1 counter) -> 2 events
    assert len(result.events) == 2
    for event in result.events:
        assert event.priority == EventPriority.ERROR
    events_by_iface = {event.data["interface"]: event for event in result.events}
    assert events_by_iface["ionic_0"].data["errors"] == {
        "req_rx_rmt_acc_err": 10,
        "req_tx_loc_oper_err": 3,
    }
    assert events_by_iface["mlx5_0"].data["errors"] == {"packet_seq_err": 7}


def test_critical_error_detected(rdma_analyzer):
    stats = [
        RdmaStatistics(
            ifname="bnxt_re_test",
            port=1,
            vendor_statistics=Thor2RdmaStatistics(
                unrecoverable_err=1,
                res_tx_pci_err=2,
            ),
        )
    ]
    model = RdmaDataModel(statistic_list=stats)
    result = rdma_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.ERROR
    assert "RDMA errors detected in statistics" in result.message
    # One event per interface; escalated to CRITICAL because critical counters are set.
    assert len(result.events) == 1
    assert result.events[0].priority == EventPriority.CRITICAL
    assert result.events[0].data["errors"] == {"unrecoverable_err": 1, "res_tx_pci_err": 2}


def test_empty_statistics(rdma_analyzer):
    model = RdmaDataModel(statistic_list=[], link_list=[])
    result = rdma_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.WARNING
    assert result.message == "No RDMA devices found"


def test_multiple_interfaces_with_errors(rdma_analyzer, example_stat_dicts):
    stats_multi_errors = _build_stats(example_stat_dicts)
    stats_multi_errors[0].vendor_statistics.req_rx_pkt_seq_err = 15
    stats_multi_errors[2].vendor_statistics.tx_rdma_ack_timeout = 8
    stats_multi_errors[8].vendor_statistics.out_of_buffer = 100
    model = RdmaDataModel(statistic_list=stats_multi_errors)
    result = rdma_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.ERROR
    assert len(result.events) == 3
    interfaces = {event.data["interface"] for event in result.events}
    assert len(interfaces) == 3


def test_all_error_types(rdma_analyzer):
    stats = [
        RdmaStatistics(
            ifname="ionic_test",
            port=1,
            vendor_statistics=PollaraRdmaStatistics(
                req_rx_pkt_seq_err=1,
                req_tx_loc_oper_err=1,
            ),
        ),
        RdmaStatistics(
            ifname="mlx5_test",
            port=1,
            vendor_statistics=Cx7RdmaStatistics(
                packet_seq_err=1,
            ),
        ),
    ]
    model = RdmaDataModel(statistic_list=stats)
    result = rdma_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.ERROR
    assert len(result.events) == 2
    interfaces = {event.data["interface"] for event in result.events}
    assert interfaces == {"ionic_test", "mlx5_test"}


def test_zero_errors_are_ignored(rdma_analyzer):
    stats = [
        RdmaStatistics(
            ifname="ionic_test",
            port=1,
            vendor_statistics=PollaraRdmaStatistics(
                req_rx_pkt_seq_err=0,
                req_rx_rnr_retry_err=0,
                tx_rdma_ack_timeout=0,
            ),
        ),
        RdmaStatistics(
            ifname="mlx5_test",
            port=1,
            vendor_statistics=Cx7RdmaStatistics(
                packet_seq_err=0,
                out_of_buffer=0,
            ),
        ),
    ]
    model = RdmaDataModel(statistic_list=stats)
    result = rdma_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.OK
    assert len(result.events) == 0


def test_rdma_link_all_active(rdma_analyzer, clean_stats):
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
    assert result.status == ExecutionStatus.OK


def test_rdma_link_empty_list(rdma_analyzer, clean_stats):
    model = RdmaDataModel(statistic_list=clean_stats, link_list=[])
    result = rdma_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.OK
    assert result.message == "No RDMA errors detected in statistics"


def test_rdma_link_multiple_interfaces(rdma_analyzer, clean_stats):
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


def test_netdev_used_in_event(rdma_analyzer):
    stats = [
        RdmaStatistics(
            ifname="ionic_0",
            netdev="benic8p1",
            port=1,
            vendor_statistics=PollaraRdmaStatistics(req_rx_pkt_seq_err=4),
        )
    ]
    model = RdmaDataModel(statistic_list=stats)
    result = rdma_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.ERROR
    assert len(result.events) == 1
    assert result.events[0].data["netdev"] == "benic8p1"
    assert result.events[0].description == "RDMA error detected"


def test_exclusion_regex_skips_interface(rdma_analyzer):
    stats = [
        RdmaStatistics(
            ifname="ionic_0",
            netdev="benic8p1",
            port=1,
            vendor_statistics=PollaraRdmaStatistics(req_rx_pkt_seq_err=4),
        ),
        RdmaStatistics(
            ifname="mlx5_0",
            netdev="benic9p1",
            port=1,
            vendor_statistics=Cx7RdmaStatistics(packet_seq_err=2),
        ),
    ]
    model = RdmaDataModel(statistic_list=stats)
    result = rdma_analyzer.analyze_data(model, RdmaAnalyzerArgs(exclusion_regex=["benic8"]))
    assert result.status == ExecutionStatus.ERROR
    # ionic_0 (netdev benic8p1) is excluded; only the mlx5_0 error is reported.
    assert len(result.events) == 1
    assert result.events[0].data["interface"] == "mlx5_0"
    assert "1 skipped" in result.message


def test_exclusion_regex_all_skipped(rdma_analyzer):
    stats = [
        RdmaStatistics(
            ifname="ionic_0",
            netdev="benic8p1",
            port=1,
            vendor_statistics=PollaraRdmaStatistics(req_rx_pkt_seq_err=4),
        )
    ]
    model = RdmaDataModel(statistic_list=stats)
    result = rdma_analyzer.analyze_data(model, RdmaAnalyzerArgs(exclusion_regex=["benic8p1"]))
    assert result.status == ExecutionStatus.OK
    assert len(result.events) == 0
    assert "1 skipped" in result.message
