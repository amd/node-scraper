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
import pytest

from nodescraper.enums import EventPriority, ExecutionStatus
from nodescraper.plugins.inband.network.ethtool_vendor import (
    EthtoolStatistics,
    Thor2EthtoolStatistics,
)
from nodescraper.plugins.inband.network.network_analyzer import NetworkAnalyzer
from nodescraper.plugins.inband.network.networkdata import (
    EthtoolInfo,
    NetworkDataModel,
)


@pytest.fixture
def network_analyzer(system_info):
    return NetworkAnalyzer(system_info)


@pytest.fixture
def clean_ethtool_info():
    """EthtoolInfo with no vendor statistics."""
    return EthtoolInfo(
        interface="eth0",
        raw_output="dummy output",
    )


@pytest.fixture
def clean_network_model(clean_ethtool_info):
    """Network data with no errors (all counters zero)."""
    return NetworkDataModel(
        ethtool_info={
            "eth0": clean_ethtool_info,
        }
    )


def test_no_errors_detected(network_analyzer, clean_network_model):
    """Test with nominal data that has no errors."""
    result = network_analyzer.analyze_data(clean_network_model)
    assert result.status == ExecutionStatus.OK
    assert "No network errors detected" in result.message
    assert len(result.events) == 0


def test_empty_ethtool_info(network_analyzer):
    """Test with empty ethtool_info and no RDMA ethtool: WARNING and message logged."""
    model = NetworkDataModel(ethtool_info={})
    result = network_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.WARNING
    assert result.message == "No network devices found"


def test_rdma_ethtool_vendor_error_only(network_analyzer):
    """Vendor ethtool: error-tier counter raises ERROR."""
    stat = EthtoolStatistics(
        netdev="eth0",
        driver="bnxt_en",
        vendor_statistics=Thor2EthtoolStatistics(rx_fcs_err_frames=4),
    )
    model = NetworkDataModel(ethtool_info={}, ethtool_statistics=[stat])
    result = network_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.ERROR
    assert "Network errors detected" in result.message
    assert len(result.events) == 1
    assert result.events[0].data["error_field"] == "rx_fcs_err_frames"
    assert result.events[0].data["error_count"] == 4
    assert result.events[0].priority == EventPriority.ERROR


def test_rdma_ethtool_vendor_warning_only(network_analyzer):
    """Vendor ethtool: only warning-tier counters -> WARNING status."""
    stat = EthtoolStatistics(
        netdev="eth0",
        driver="bnxt_en",
        vendor_statistics=Thor2EthtoolStatistics(rx_pause_frames=2),
    )
    model = NetworkDataModel(ethtool_info={}, ethtool_statistics=[stat])
    result = network_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.WARNING
    assert "warning counters" in result.message
    assert len(result.events) == 1
    assert result.events[0].data["error_field"] == "rx_pause_frames"
    assert result.events[0].priority == EventPriority.WARNING


def test_thor2_tx_pause_counters_are_warning_tier():
    """Sync with error-scraper: TX pause/PFC counters are warning-tier, not error-tier."""
    assert "tx_pfc_frames" in Thor2EthtoolStatistics.warning_fields
    assert "tx_pfc_frames" not in Thor2EthtoolStatistics.error_fields
    assert "tx_pause_frames" in Thor2EthtoolStatistics.warning_fields
    # RX-side hard error counters remain error-tier
    assert "rx_fcs_err_frames" in Thor2EthtoolStatistics.error_fields


def test_rdma_ethtool_no_vendor_model_ok(network_analyzer):
    """Ethtool row without parsed vendor statistics is ignored by vendor path."""
    stat = EthtoolStatistics(netdev="eth0", driver="unknown", vendor_statistics=None)
    model = NetworkDataModel(ethtool_info={}, ethtool_statistics=[stat])
    result = network_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.OK
    assert len(result.events) == 0


def test_queue_counter_error_detected(network_analyzer):
    """A non-zero per-queue error counter (e.g. rx_discards) is flagged as ERROR."""
    stat = EthtoolStatistics(
        netdev="benic1p1",
        driver="bnxt0",
        vendor_statistics=Thor2EthtoolStatistics(),
        queue_statistics={
            "[0]: rx_ucast_packets": 100,  # benign, ignored
            "[0]: rx_discards": 5,  # error
            "[3]: tx_errors": 2,  # error
        },
    )
    model = NetworkDataModel(ethtool_info={}, ethtool_statistics=[stat])
    result = network_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.ERROR
    assert "Network errors detected" in result.message

    queue_events = [e for e in result.events if e.description == "Ethtool queue error detected"]
    assert len(queue_events) == 2
    flagged = {e.data["error_field"] for e in queue_events}
    assert flagged == {"[0]: rx_discards", "[3]: tx_errors"}
    assert all(e.priority == EventPriority.ERROR for e in queue_events)


def test_queue_counter_thor2_specific_error_fields(network_analyzer):
    """Each curated Thor2 per-queue error pattern flags its non-zero counter as ERROR."""
    stat = EthtoolStatistics(
        netdev="benic1p1",
        driver="bnxt0",
        vendor_statistics=Thor2EthtoolStatistics(),
        queue_statistics={
            "[0]: rx_discards": 1,
            "[1]: rx_errors": 2,
            "[2]: tx_errors": 3,
            "[3]: rx_l4_csum_errors": 4,
            "[4]: rx_buf_errors": 5,
            "[5]: so_txtime_cmpl_errors": 6,
            "[6]: missed_irqs": 7,
            "[7]: xsk_rx_redirect_fail": 8,
            "[8]: xsk_rx_alloc_fail": 9,
            "[9]: xsk_rx_no_room": 10,
            "[10]: xsk_tx_ring_full": 11,
            # benign counters must NOT be flagged
            "[0]: rx_ucast_packets": 12345,
            "[0]: tx_ucast_bytes": 67890,
        },
    )
    model = NetworkDataModel(ethtool_info={}, ethtool_statistics=[stat])
    result = network_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.ERROR

    error_events = [e for e in result.events if e.description == "Ethtool queue error detected"]
    flagged = {e.data["error_field"] for e in error_events}
    assert flagged == {
        "[0]: rx_discards",
        "[1]: rx_errors",
        "[2]: tx_errors",
        "[3]: rx_l4_csum_errors",
        "[4]: rx_buf_errors",
        "[5]: so_txtime_cmpl_errors",
        "[6]: missed_irqs",
        "[7]: xsk_rx_redirect_fail",
        "[8]: xsk_rx_alloc_fail",
        "[9]: xsk_rx_no_room",
        "[10]: xsk_tx_ring_full",
    }
    assert "[0]: rx_ucast_packets" not in flagged
    assert "[0]: tx_ucast_bytes" not in flagged
    assert all(e.priority == EventPriority.ERROR for e in error_events)


def test_queue_counter_benign_not_reported(network_analyzer):
    """Non-zero benign per-queue counters (packets/bytes) do not raise errors."""
    stat = EthtoolStatistics(
        netdev="benic1p1",
        driver="bnxt0",
        vendor_statistics=Thor2EthtoolStatistics(),
        queue_statistics={
            "[0]: rx_ucast_packets": 12345,
            "[0]: tx_ucast_bytes": 67890,
        },
    )
    model = NetworkDataModel(ethtool_info={}, ethtool_statistics=[stat])
    result = network_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.OK
    assert len(result.events) == 0


def test_queue_counter_zero_not_reported(network_analyzer):
    """A per-queue error counter that is zero does not raise an error."""
    stat = EthtoolStatistics(
        netdev="benic1p1",
        driver="bnxt0",
        vendor_statistics=Thor2EthtoolStatistics(),
        queue_statistics={"[0]: rx_discards": 0, "[1]: tx_errors": 0},
    )
    model = NetworkDataModel(ethtool_info={}, ethtool_statistics=[stat])
    result = network_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.OK
    assert len(result.events) == 0


def test_queue_counter_warning_detected(network_analyzer):
    """A non-zero warning-tier per-queue counter (e.g. rx_resets) -> WARNING."""
    stat = EthtoolStatistics(
        netdev="benic1p1",
        driver="bnxt0",
        vendor_statistics=Thor2EthtoolStatistics(),
        queue_statistics={
            "[0]: rx_ucast_packets": 100,  # benign, ignored
            "[0]: rx_resets": 3,  # warning-tier
        },
    )
    model = NetworkDataModel(ethtool_info={}, ethtool_statistics=[stat])
    result = network_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.WARNING
    assert "warning counters" in result.message
    warn_events = [e for e in result.events if e.description == "Ethtool queue warning detected"]
    assert len(warn_events) == 1
    assert warn_events[0].data["error_field"] == "[0]: rx_resets"
    assert warn_events[0].priority == EventPriority.WARNING


def test_queue_counter_error_precedence_over_warning(network_analyzer):
    """When both error and warning per-queue counters are non-zero, status is ERROR."""
    stat = EthtoolStatistics(
        netdev="benic1p1",
        driver="bnxt0",
        vendor_statistics=Thor2EthtoolStatistics(),
        queue_statistics={
            "[0]: rx_discards": 5,  # error-tier
            "[0]: rx_resets": 3,  # warning-tier
        },
    )
    model = NetworkDataModel(ethtool_info={}, ethtool_statistics=[stat])
    result = network_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.ERROR
    err_events = [e for e in result.events if e.description == "Ethtool queue error detected"]
    warn_events = [e for e in result.events if e.description == "Ethtool queue warning detected"]
    assert {e.data["error_field"] for e in err_events} == {"[0]: rx_discards"}
    assert {e.data["error_field"] for e in warn_events} == {"[0]: rx_resets"}


def test_queue_counter_empty_warning_list_skips_warning_check(network_analyzer, monkeypatch):
    """An empty queue_warning_regex skips warning checking; error checking still runs."""
    monkeypatch.setattr(Thor2EthtoolStatistics, "queue_warning_regex", [])
    stat = EthtoolStatistics(
        netdev="benic1p1",
        driver="bnxt0",
        vendor_statistics=Thor2EthtoolStatistics(),
        queue_statistics={
            "[0]: rx_resets": 3,  # would be a warning, but warning list is empty
            "[0]: rx_discards": 5,  # still flagged as an error
        },
    )
    model = NetworkDataModel(ethtool_info={}, ethtool_statistics=[stat])
    result = network_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.ERROR
    warn_events = [e for e in result.events if e.description == "Ethtool queue warning detected"]
    assert warn_events == []
    err_events = [e for e in result.events if e.description == "Ethtool queue error detected"]
    assert {e.data["error_field"] for e in err_events} == {"[0]: rx_discards"}


def test_queue_counter_empty_error_list_skips_error_check(network_analyzer, monkeypatch):
    """An empty queue_error_regex skips error checking; warning checking still runs."""
    monkeypatch.setattr(Thor2EthtoolStatistics, "queue_error_regex", [])
    stat = EthtoolStatistics(
        netdev="benic1p1",
        driver="bnxt0",
        vendor_statistics=Thor2EthtoolStatistics(),
        queue_statistics={
            "[0]: rx_discards": 5,  # would be an error, but error list is empty
            "[0]: rx_resets": 3,  # still flagged as a warning
        },
    )
    model = NetworkDataModel(ethtool_info={}, ethtool_statistics=[stat])
    result = network_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.WARNING
    err_events = [e for e in result.events if e.description == "Ethtool queue error detected"]
    assert err_events == []
    warn_events = [e for e in result.events if e.description == "Ethtool queue warning detected"]
    assert {e.data["error_field"] for e in warn_events} == {"[0]: rx_resets"}


def test_queue_counter_both_lists_empty_skips_all_checks(network_analyzer, monkeypatch):
    """Empty error and warning lists skip per-queue checking entirely (status OK)."""
    monkeypatch.setattr(Thor2EthtoolStatistics, "queue_error_regex", [])
    monkeypatch.setattr(Thor2EthtoolStatistics, "queue_warning_regex", [])
    stat = EthtoolStatistics(
        netdev="benic1p1",
        driver="bnxt0",
        vendor_statistics=Thor2EthtoolStatistics(),
        queue_statistics={"[0]: rx_discards": 5, "[0]: rx_resets": 3},
    )
    model = NetworkDataModel(ethtool_info={}, ethtool_statistics=[stat])
    result = network_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.OK
    assert len(result.events) == 0
