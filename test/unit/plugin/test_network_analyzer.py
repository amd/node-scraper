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
from nodescraper.plugins.inband.network.analyzer_args import NetworkAnalyzerArgs
from nodescraper.plugins.inband.network.ethtool_vendor import (
    EthtoolStatistics,
    Thor2EthtoolStatistics,
)
from nodescraper.plugins.inband.network.network_analyzer import NetworkAnalyzer
from nodescraper.plugins.inband.network.networkdata import (
    EthtoolInfo,
    NetworkDataModel,
)

# Built-in regex defaults were removed; the vendor ethtool models own RDMA counter
# classification. These custom patterns exercise the user-supplied regex path.
CUSTOM_REGEX = [
    {
        "regex": r"^custom_err_\d+$",
        "message": "custom err counter non-zero",
        "event_category": "NETWORK",
    }
]


@pytest.fixture
def network_analyzer(system_info):
    return NetworkAnalyzer(system_info)


@pytest.fixture
def clean_ethtool_info():
    """EthtoolInfo with no errors (all counters zero)."""
    return EthtoolInfo(
        interface="eth0",
        raw_output="dummy output",
        statistics={
            "tx_pfc_frames": "0",
            "tx_pfc_ena_frames_pri0": "0",
            "tx_pfc_ena_frames_pri1": "0",
            "tx_pfc_ena_frames_pri2": "0",
            "tx_pfc_ena_frames_pri3": "0",
            "tx_pfc_ena_frames_pri4": "0",
            "tx_pfc_ena_frames_pri5": "0",
            "tx_pfc_ena_frames_pri6": "0",
            "tx_pfc_ena_frames_pri7": "0",
            "pfc_pri0_tx_transitions": "0",
            "pfc_pri1_tx_transitions": "0",
            "pfc_pri2_tx_transitions": "0",
            "pfc_pri3_tx_transitions": "0",
            "pfc_pri4_tx_transitions": "0",
            "pfc_pri5_tx_transitions": "0",
            "pfc_pri6_tx_transitions": "0",
            "pfc_pri7_tx_transitions": "0",
            "some_other_stat": "100",  # Should be ignored
            "rx_bytes": "1234567",  # Should be ignored
        },
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


def test_single_custom_match_detected(network_analyzer):
    """A single non-zero counter matched by a user-supplied custom regex reports as ERROR."""
    ethtool = EthtoolInfo(
        interface="eth0",
        raw_output="dummy",
        statistics={"custom_err_0": "5"},
    )
    model = NetworkDataModel(ethtool_info={"eth0": ethtool})
    result = network_analyzer.analyze_data(
        model, args=NetworkAnalyzerArgs(error_regex=CUSTOM_REGEX)
    )
    assert result.status == ExecutionStatus.ERROR
    assert "errors detected" in result.message
    assert len(result.events) == 1
    assert result.events[0].description == "Network error detected on eth0: [custom_err_0]"
    assert result.events[0].priority == EventPriority.ERROR
    assert result.events[0].data["errors"] == {"custom_err_0": 5}
    assert result.events[0].data["interface"] == "eth0"


def test_multiple_matches_same_interface(network_analyzer):
    """Multiple non-zero counters on one interface produce a single grouped event."""
    ethtool = EthtoolInfo(
        interface="eth0",
        raw_output="dummy",
        statistics={"custom_err_0": "10", "custom_err_1": "3", "custom_err_2": "7"},
    )
    model = NetworkDataModel(ethtool_info={"eth0": ethtool})
    result = network_analyzer.analyze_data(
        model, args=NetworkAnalyzerArgs(error_regex=CUSTOM_REGEX)
    )
    assert result.status == ExecutionStatus.ERROR
    assert "errors detected" in result.message
    assert len(result.events) == 1  # one event per interface
    assert result.events[0].priority == EventPriority.ERROR
    # Check all 3 counters are present
    assert len(result.events[0].data["errors"]) == 3
    assert result.events[0].data["errors"]["custom_err_0"] == 10
    assert result.events[0].data["errors"]["custom_err_1"] == 3
    assert result.events[0].data["errors"]["custom_err_2"] == 7


def test_multiple_interfaces_with_matches(network_analyzer):
    """Test with custom-regex matches across multiple interfaces."""
    eth0 = EthtoolInfo(
        interface="eth0",
        raw_output="dummy",
        statistics={
            "custom_err_0": "15",
            "custom_err_1": "0",
        },
    )
    eth1 = EthtoolInfo(
        interface="eth1",
        raw_output="dummy",
        statistics={
            "custom_err_3": "8",
        },
    )
    eth2 = EthtoolInfo(
        interface="eth2",
        raw_output="dummy",
        statistics={
            "custom_err_7": "100",
        },
    )
    model = NetworkDataModel(
        ethtool_info={
            "eth0": eth0,
            "eth1": eth1,
            "eth2": eth2,
        }
    )
    result = network_analyzer.analyze_data(
        model, args=NetworkAnalyzerArgs(error_regex=CUSTOM_REGEX)
    )
    assert result.status == ExecutionStatus.ERROR
    assert len(result.events) == 3
    interfaces = {event.data["interface"] for event in result.events}
    assert interfaces == {"eth0", "eth1", "eth2"}


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


def test_custom_regex_matches_multi_digit_suffixes(network_analyzer):
    """Test that a user-supplied \\d+ pattern matches single- and double-digit suffixes."""
    ethtool = EthtoolInfo(
        interface="eth0",
        raw_output="dummy",
        statistics={
            "custom_err_0": "1",
            "custom_err_3": "2",
            "custom_err_7": "3",
            "custom_err_10": "4",  # Test double-digit
            "custom_err_15": "5",  # Test double-digit
        },
    )
    model = NetworkDataModel(ethtool_info={"eth0": ethtool})
    result = network_analyzer.analyze_data(
        model, args=NetworkAnalyzerArgs(error_regex=CUSTOM_REGEX)
    )
    assert result.status == ExecutionStatus.ERROR
    assert len(result.events) == 1
    # All 5 counters should be detected
    assert len(result.events[0].data["errors"]) == 5


def test_non_numeric_values_ignored(network_analyzer):
    """Test that non-numeric values in statistics are gracefully ignored."""
    ethtool = EthtoolInfo(
        interface="eth0",
        raw_output="dummy",
        statistics={
            "custom_err_0": "N/A",  # Non-numeric
            "custom_err_1": "invalid",  # Non-numeric
            "custom_err_2": "5",  # Valid
        },
    )
    model = NetworkDataModel(ethtool_info={"eth0": ethtool})
    result = network_analyzer.analyze_data(
        model, args=NetworkAnalyzerArgs(error_regex=CUSTOM_REGEX)
    )
    assert result.status == ExecutionStatus.ERROR
    assert len(result.events) == 1
    # Only the valid numeric counter should be reported
    assert len(result.events[0].data["errors"]) == 1
    assert result.events[0].data["errors"]["custom_err_2"] == 5


def test_zero_values_not_reported(network_analyzer):
    """Test that zero values are not reported as errors."""
    ethtool = EthtoolInfo(
        interface="eth0",
        raw_output="dummy",
        statistics={
            "custom_err_0": "0",
            "custom_err_1": "0",
            "custom_err_2": "0",
        },
    )
    model = NetworkDataModel(ethtool_info={"eth0": ethtool})
    result = network_analyzer.analyze_data(
        model, args=NetworkAnalyzerArgs(error_regex=CUSTOM_REGEX)
    )
    assert result.status == ExecutionStatus.OK
    assert len(result.events) == 0


def test_non_matching_fields_ignored(network_analyzer):
    """Test that statistics not matching error patterns are ignored."""
    ethtool = EthtoolInfo(
        interface="eth0",
        raw_output="dummy",
        statistics={
            "rx_bytes": "999999999",  # High value but not a matched field
            "tx_bytes": "888888888",  # High value but not a matched field
            "some_random_counter": "12345",  # Not a matched field
            "custom_err_0": "5",  # This SHOULD be detected
        },
    )
    model = NetworkDataModel(ethtool_info={"eth0": ethtool})
    result = network_analyzer.analyze_data(
        model, args=NetworkAnalyzerArgs(error_regex=CUSTOM_REGEX)
    )
    assert result.status == ExecutionStatus.ERROR
    assert len(result.events) == 1
    # Only custom_err_0 should be reported
    assert len(result.events[0].data["errors"]) == 1
    assert "custom_err_0" in result.events[0].data["errors"]


def test_mixed_interfaces_with_and_without_errors(network_analyzer):
    """Test with some interfaces having matches and others clean."""
    eth0_error = EthtoolInfo(
        interface="eth0",
        raw_output="dummy",
        statistics={
            "custom_err_0": "10",
        },
    )
    eth1_clean = EthtoolInfo(
        interface="eth1",
        raw_output="dummy",
        statistics={
            "custom_err_0": "0",
            "custom_err_1": "0",
        },
    )
    eth2_error = EthtoolInfo(
        interface="eth2",
        raw_output="dummy",
        statistics={
            "custom_err_5": "20",
        },
    )
    model = NetworkDataModel(
        ethtool_info={
            "eth0": eth0_error,
            "eth1": eth1_clean,
            "eth2": eth2_error,
        }
    )
    result = network_analyzer.analyze_data(
        model, args=NetworkAnalyzerArgs(error_regex=CUSTOM_REGEX)
    )
    assert result.status == ExecutionStatus.ERROR
    # Only 2 events (eth0 and eth2), eth1 should not generate an event
    assert len(result.events) == 2
    interfaces_with_errors = {event.data["interface"] for event in result.events}
    assert interfaces_with_errors == {"eth0", "eth2"}


def test_custom_error_regex_detected(network_analyzer):
    """Test that user-supplied custom regex patterns are applied (no built-in defaults)."""
    ethtool = EthtoolInfo(
        interface="eth0",
        raw_output="dummy",
        statistics={
            "custom_tx_drops": "9",  # Matched via custom regex only
            "tx_pfc_frames": "0",  # No built-in pattern; ignored unless RDMA vendor-scoped
        },
    )
    model = NetworkDataModel(ethtool_info={"eth0": ethtool})
    args = NetworkAnalyzerArgs(
        error_regex=[
            {
                "regex": r"^custom_tx_drops$",
                "message": "Custom tx drops",
                "event_category": "NETWORK",
            }
        ]
    )

    result = network_analyzer.analyze_data(model, args=args)

    assert result.status == ExecutionStatus.ERROR
    assert len(result.events) == 1
    assert result.events[0].data["interface"] == "eth0"
    assert result.events[0].data["errors"] == {"custom_tx_drops": 9}


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


def test_custom_warning_priority_regex(network_analyzer):
    """A user-supplied WARNING-priority custom pattern yields WARNING status via the regex path."""
    ethtool = EthtoolInfo(
        interface="eth0",
        raw_output="dummy",
        statistics={"custom_warn": "3"},
    )
    model = NetworkDataModel(ethtool_info={"eth0": ethtool})
    args = NetworkAnalyzerArgs(
        error_regex=[
            {
                "regex": r"^custom_warn$",
                "message": "custom warn counter",
                "event_category": "NETWORK",
                "event_priority": "WARNING",
            }
        ]
    )

    result = network_analyzer.analyze_data(model, args=args)

    assert result.status == ExecutionStatus.WARNING
    assert "warning counters" in result.message
    assert len(result.events) == 1
    assert result.events[0].priority == EventPriority.WARNING
    assert result.events[0].description == "Network warning detected on eth0: [custom_warn]"
    assert result.events[0].data["errors"] == {"custom_warn": 3}
