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
    """RDMA-scoped vendor ethtool: error-tier counter raises ERROR."""
    stat = EthtoolStatistics(
        netdev="eth0",
        rdma_ifname="bnxt0",
        vendor_statistics=Thor2EthtoolStatistics(rx_fcs_err_frames=4),
    )
    model = NetworkDataModel(ethtool_info={}, rdma_ethtool_statistics=[stat])
    result = network_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.ERROR
    assert "Network errors detected" in result.message
    assert len(result.events) == 1
    assert result.events[0].data["error_field"] == "rx_fcs_err_frames"
    assert result.events[0].data["error_count"] == 4
    assert result.events[0].priority == EventPriority.ERROR


def test_rdma_ethtool_vendor_warning_only(network_analyzer):
    """RDMA-scoped vendor ethtool: only warning-tier counters -> WARNING status."""
    stat = EthtoolStatistics(
        netdev="eth0",
        rdma_ifname="bnxt0",
        vendor_statistics=Thor2EthtoolStatistics(rx_pause_frames=2),
    )
    model = NetworkDataModel(ethtool_info={}, rdma_ethtool_statistics=[stat])
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
    """RDMA ethtool row without parsed vendor statistics is ignored by vendor path."""
    stat = EthtoolStatistics(netdev="eth0", rdma_ifname="unknown0", vendor_statistics=None)
    model = NetworkDataModel(ethtool_info={}, rdma_ethtool_statistics=[stat])
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


def test_exclusion_regex_skips_vendor_netdev(network_analyzer):
    """A netdev matching exclusion_regex is skipped on the vendor path; count noted in message."""
    stat = EthtoolStatistics(
        netdev="eth0",
        rdma_ifname="bnxt0",
        vendor_statistics=Thor2EthtoolStatistics(rx_fcs_err_frames=4),
    )
    model = NetworkDataModel(ethtool_info={}, rdma_ethtool_statistics=[stat])
    args = NetworkAnalyzerArgs(exclusion_regex=[r"^eth0$"])
    result = network_analyzer.analyze_data(model, args=args)
    assert result.status == ExecutionStatus.OK
    assert len(result.events) == 0
    assert "1 skipped" in result.message


def test_exclusion_regex_skips_regex_path_interface(network_analyzer):
    """An interface matching exclusion_regex is skipped on the user-supplied regex path."""
    ethtool = EthtoolInfo(
        interface="eth0",
        raw_output="dummy",
        statistics={"custom_err_0": "5"},
    )
    model = NetworkDataModel(ethtool_info={"eth0": ethtool})
    args = NetworkAnalyzerArgs(error_regex=CUSTOM_REGEX, exclusion_regex=[r"^eth0$"])
    result = network_analyzer.analyze_data(model, args=args)
    assert result.status == ExecutionStatus.OK
    assert len(result.events) == 0
    assert "1 skipped" in result.message


def test_exclusion_regex_partial_match_mixed(network_analyzer):
    """exclusion_regex uses search(): a substring pattern skips only matching netdevs."""
    stat_skip = EthtoolStatistics(
        netdev="bnxt_eth2",
        rdma_ifname="bnxt0",
        vendor_statistics=Thor2EthtoolStatistics(rx_fcs_err_frames=4),
    )
    stat_keep = EthtoolStatistics(
        netdev="mlx_eth3",
        rdma_ifname="mlx5_0",
        vendor_statistics=Thor2EthtoolStatistics(rx_fcs_err_frames=7),
    )
    model = NetworkDataModel(ethtool_info={}, rdma_ethtool_statistics=[stat_skip, stat_keep])
    args = NetworkAnalyzerArgs(exclusion_regex=[r"bnxt"])
    result = network_analyzer.analyze_data(model, args=args)
    # bnxt_eth2 skipped, mlx_eth3 still flagged as ERROR
    assert result.status == ExecutionStatus.ERROR
    assert len(result.events) == 1
    assert result.events[0].data["netdev"] == "mlx_eth3"
    assert "1 skipped" in result.message
