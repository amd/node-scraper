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


def test_single_error_detected(network_analyzer, clean_ethtool_info):
    """Test with data containing a single error."""
    clean_ethtool_info.statistics["tx_pfc_frames"] = "5"
    model = NetworkDataModel(ethtool_info={"eth0": clean_ethtool_info})
    result = network_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.ERROR
    assert "Network errors detected in statistics" in result.message
    assert len(result.events) == 1
    assert result.events[0].description == "Network error detected on eth0: [tx_pfc_frames]"
    assert result.events[0].priority == EventPriority.ERROR
    assert result.events[0].data["errors"] == {"tx_pfc_frames": 5}
    assert result.events[0].data["interface"] == "eth0"


def test_multiple_errors_same_interface(network_analyzer, clean_ethtool_info):
    """Test with data containing multiple errors on the same interface."""
    clean_ethtool_info.statistics["tx_pfc_frames"] = "10"
    clean_ethtool_info.statistics["tx_pfc_ena_frames_pri0"] = "3"
    clean_ethtool_info.statistics["pfc_pri2_tx_transitions"] = "7"
    model = NetworkDataModel(ethtool_info={"eth0": clean_ethtool_info})
    result = network_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.ERROR
    assert "Network errors detected in statistics" in result.message
    assert len(result.events) == 1  # one event per interface
    assert result.events[0].priority == EventPriority.ERROR
    # Check all 3 errors are present
    assert len(result.events[0].data["errors"]) == 3
    assert result.events[0].data["errors"]["tx_pfc_frames"] == 10
    assert result.events[0].data["errors"]["tx_pfc_ena_frames_pri0"] == 3
    assert result.events[0].data["errors"]["pfc_pri2_tx_transitions"] == 7


def test_multiple_interfaces_with_errors(network_analyzer):
    """Test with errors across multiple interfaces."""
    eth0 = EthtoolInfo(
        interface="eth0",
        raw_output="dummy",
        statistics={
            "tx_pfc_frames": "15",
            "tx_pfc_ena_frames_pri1": "0",
        },
    )
    eth1 = EthtoolInfo(
        interface="eth1",
        raw_output="dummy",
        statistics={
            "pfc_pri3_tx_transitions": "8",
        },
    )
    eth2 = EthtoolInfo(
        interface="eth2",
        raw_output="dummy",
        statistics={
            "tx_pfc_ena_frames_pri7": "100",
        },
    )
    model = NetworkDataModel(
        ethtool_info={
            "eth0": eth0,
            "eth1": eth1,
            "eth2": eth2,
        }
    )
    result = network_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.ERROR
    assert len(result.events) == 3
    interfaces = {event.data["interface"] for event in result.events}
    assert interfaces == {"eth0", "eth1", "eth2"}


def test_empty_ethtool_info(network_analyzer):
    """Test with empty ethtool_info: WARNING and message logged."""
    model = NetworkDataModel(ethtool_info={})
    result = network_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.WARNING
    assert result.message == "No network devices found"


def test_regex_patterns_priority_numbers(network_analyzer):
    """Test that regex patterns match various priority numbers (0-7 and beyond)."""
    ethtool = EthtoolInfo(
        interface="eth0",
        raw_output="dummy",
        statistics={
            "tx_pfc_ena_frames_pri0": "1",
            "tx_pfc_ena_frames_pri3": "2",
            "tx_pfc_ena_frames_pri7": "3",
            "tx_pfc_ena_frames_pri10": "4",  # Test double-digit
            "pfc_pri0_tx_transitions": "5",
            "pfc_pri5_tx_transitions": "6",
            "pfc_pri15_tx_transitions": "7",  # Test double-digit
        },
    )
    model = NetworkDataModel(ethtool_info={"eth0": ethtool})
    result = network_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.ERROR
    assert len(result.events) == 1
    # All 7 errors should be detected
    assert len(result.events[0].data["errors"]) == 7


def test_non_numeric_values_ignored(network_analyzer):
    """Test that non-numeric values in statistics are gracefully ignored."""
    ethtool = EthtoolInfo(
        interface="eth0",
        raw_output="dummy",
        statistics={
            "tx_pfc_frames": "N/A",  # Non-numeric
            "tx_pfc_ena_frames_pri0": "invalid",  # Non-numeric
            "pfc_pri1_tx_transitions": "5",  # Valid error
        },
    )
    model = NetworkDataModel(ethtool_info={"eth0": ethtool})
    result = network_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.ERROR
    assert len(result.events) == 1
    # Only the valid numeric error should be reported
    assert len(result.events[0].data["errors"]) == 1
    assert result.events[0].data["errors"]["pfc_pri1_tx_transitions"] == 5


def test_zero_values_not_reported(network_analyzer):
    """Test that zero values are not reported as errors."""
    ethtool = EthtoolInfo(
        interface="eth0",
        raw_output="dummy",
        statistics={
            "tx_pfc_frames": "0",
            "tx_pfc_ena_frames_pri0": "0",
            "pfc_pri1_tx_transitions": "0",
        },
    )
    model = NetworkDataModel(ethtool_info={"eth0": ethtool})
    result = network_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.OK
    assert len(result.events) == 0


def test_non_matching_fields_ignored(network_analyzer):
    """Test that statistics not matching error patterns are ignored."""
    ethtool = EthtoolInfo(
        interface="eth0",
        raw_output="dummy",
        statistics={
            "rx_bytes": "999999999",  # High value but not an error field
            "tx_bytes": "888888888",  # High value but not an error field
            "some_random_counter": "12345",  # Not an error field
            "tx_pfc_frames": "5",  # This SHOULD be detected
        },
    )
    model = NetworkDataModel(ethtool_info={"eth0": ethtool})
    result = network_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.ERROR
    assert len(result.events) == 1
    # Only tx_pfc_frames should be reported
    assert len(result.events[0].data["errors"]) == 1
    assert "tx_pfc_frames" in result.events[0].data["errors"]


def test_mixed_interfaces_with_and_without_errors(network_analyzer):
    """Test with some interfaces having errors and others clean."""
    eth0_error = EthtoolInfo(
        interface="eth0",
        raw_output="dummy",
        statistics={
            "tx_pfc_frames": "10",
        },
    )
    eth1_clean = EthtoolInfo(
        interface="eth1",
        raw_output="dummy",
        statistics={
            "tx_pfc_frames": "0",
            "tx_pfc_ena_frames_pri0": "0",
        },
    )
    eth2_error = EthtoolInfo(
        interface="eth2",
        raw_output="dummy",
        statistics={
            "pfc_pri5_tx_transitions": "20",
        },
    )
    model = NetworkDataModel(
        ethtool_info={
            "eth0": eth0_error,
            "eth1": eth1_clean,
            "eth2": eth2_error,
        }
    )
    result = network_analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.ERROR
    # Only 2 events (eth0 and eth2), eth1 should not generate an event
    assert len(result.events) == 2
    interfaces_with_errors = {event.data["interface"] for event in result.events}
    assert interfaces_with_errors == {"eth0", "eth2"}
