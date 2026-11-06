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
"""Unit tests for PcieAnalyzer non-AMD device and NIC checks."""

import pytest

from nodescraper.plugins.inband.pcie.analyzer_args import PcieAnalyzerArgs
from nodescraper.plugins.inband.pcie.pcie_analyzer import PcieAnalyzer
from nodescraper.plugins.inband.pcie.pcie_data import (
    CapabilityEnum,
    PcieCfgSpace,
    PcieDataModel,
    PcieExp,
)

# Detected Parity Error lives at bit 15 of the Type 0 Status Register.
_STATUS_DET_PARITY_ERR = 1 << 15

_OTHER_DEVICE_BDF = "0000:02:00.0"  # e.g. a non-AMD NIC

_ANALYZE_OTHER_DESC = "Analyzing other PCI devices"
_STATUS_ERR_DESC = "PCI Express Status register errors were detected"


@pytest.fixture
def analyzer(system_info):
    return PcieAnalyzer(system_info=system_info)


def _add_pcie_exp(cfg: PcieCfgSpace, lnk_stat_val: int = 0, lnk_cap2_val: int = 0) -> PcieCfgSpace:
    """Attach a fully-populated PCI Express capability so the device counts as PCIe."""
    pcie_exp = PcieExp()
    # Populate every register so the capability structure validates as complete.
    for _, reg in pcie_exp.iter_regs():
        reg.val = 0
    pcie_exp.lnk_stat_reg.val = lnk_stat_val
    pcie_exp.lnk_cap_2_reg.val = lnk_cap2_val
    cfg.cap_structure[CapabilityEnum.PCIE_EXP] = pcie_exp
    return cfg


def _cfg_space_with_status_parity_error() -> PcieCfgSpace:
    """Build a config space for a non-AMD PCIe device with a Detected Parity Error set."""
    cfg = PcieCfgSpace()
    # Setting the register value propagates to all bit fields automatically.
    cfg.type_0_configuration.status.val = _STATUS_DET_PARITY_ERR
    return _add_pcie_exp(cfg)


def _clean_cfg_space() -> PcieCfgSpace:
    """Build a config space for a non-AMD PCIe device with no status errors."""
    cfg = PcieCfgSpace()
    cfg.type_0_configuration.status.val = 0
    return _add_pcie_exp(cfg)


def _descriptions(result):
    return [event.description for event in result.events]


def test_other_devices_not_analyzed_when_flag_disabled(analyzer):
    """Default behavior: with analyze_other_devices=False, non-AMD devices are ignored."""
    data = PcieDataModel(
        pcie_cfg_space={},
        other_pcie_cfg_space={_OTHER_DEVICE_BDF: _cfg_space_with_status_parity_error()},
    )
    args = PcieAnalyzerArgs(analyze_other_devices=False)

    result = analyzer.analyze_data(data, args)

    descriptions = _descriptions(result)
    assert _ANALYZE_OTHER_DESC not in descriptions
    # The parity error on the non-AMD device must NOT be reported when disabled.
    assert _STATUS_ERR_DESC not in descriptions


def test_other_devices_status_error_detected_when_flag_enabled(analyzer):
    """With analyze_other_devices=True, a status error on a non-AMD device is reported."""
    data = PcieDataModel(
        pcie_cfg_space={},
        other_pcie_cfg_space={_OTHER_DEVICE_BDF: _cfg_space_with_status_parity_error()},
    )
    args = PcieAnalyzerArgs(analyze_other_devices=True)

    result = analyzer.analyze_data(data, args)

    descriptions = _descriptions(result)
    assert _ANALYZE_OTHER_DESC in descriptions
    # The parity error on the non-AMD device is surfaced.
    assert _STATUS_ERR_DESC in descriptions
    parity_events = [
        e
        for e in result.events
        if e.description == _STATUS_ERR_DESC and e.data.get("bdf") == _OTHER_DEVICE_BDF
    ]
    assert parity_events, "Expected a status error event for the non-AMD BDF"


def test_other_devices_clean_reports_no_status_error(analyzer):
    """A clean non-AMD device produces no status-error event even when analysis is enabled."""
    data = PcieDataModel(
        pcie_cfg_space={},
        other_pcie_cfg_space={_OTHER_DEVICE_BDF: _clean_cfg_space()},
    )
    args = PcieAnalyzerArgs(analyze_other_devices=True)

    result = analyzer.analyze_data(data, args)

    descriptions = _descriptions(result)
    assert _ANALYZE_OTHER_DESC in descriptions
    assert _STATUS_ERR_DESC not in descriptions


def test_enabled_flag_without_other_data_does_not_crash(analyzer):
    """Enabling the flag with no other_pcie_cfg_space is a no-op (no crash, no marker)."""
    data = PcieDataModel(pcie_cfg_space={})
    args = PcieAnalyzerArgs(analyze_other_devices=True)

    result = analyzer.analyze_data(data, args)

    assert _ANALYZE_OTHER_DESC not in _descriptions(result)


# PCI base class codes (config space offset 0x0B).
_CLASS_NETWORK = 0x02
_CLASS_STORAGE = 0x01
_CLASS_PROCESSING_ACCEL = 0x12

# lnk_stat_reg packed values: curr_lnk_speed in bits 0-3, neg_lnk_width in bits 4-9.
_LNK_STAT_GEN5_X16 = (16 << 4) | 5  # 0x105
_LNK_STAT_GEN4_X16 = (16 << 4) | 4  # 0x104
# lnk_cap_2_reg supported_lnk_speed_vec occupies bits 1-6; 0b11111 << 1 = gens 1-5.
_LNK_CAP2_GENS_1_5 = 0b11111 << 1  # 0x3E

_NIC_COUNT_MISMATCH = "NIC count mismatch"
_NIC_COUNT_MATCH = "NIC count matches expected"
_LINK_SPEED_ERR = "Unexpected link speed detected"
_LINK_WIDTH_ERR = "Unexpected link width detected"

_NIC_BDF = "0000:02:00.0"


def _cfg_with_class(base_class, vendor_id=None, device_id=None) -> PcieCfgSpace:
    """Build a config space with a specific PCI base class (and optional vendor/device)."""
    cfg = PcieCfgSpace()
    t0 = cfg.type_0_configuration
    t0.class_code.val = base_class
    if vendor_id is not None:
        t0.vendor_id.val = vendor_id
    if device_id is not None:
        t0.device_id.val = device_id
    return cfg


def _nic_cfg_with_link(lnk_stat_val, lnk_cap2_val) -> PcieCfgSpace:
    """Build a NIC (class 0x02) config space with a fully-populated PCIe Express cap."""
    return _add_pcie_exp(_cfg_with_class(_CLASS_NETWORK), lnk_stat_val, lnk_cap2_val)


def test_bucket_devices_classifies_gpu_nic_other(analyzer):
    """Devices are bucketed by class code: AMD accelerator -> GPU, 0x02 -> NIC, else OTHER."""
    data = PcieDataModel(
        pcie_cfg_space={
            "0000:01:00.0": _cfg_with_class(
                _CLASS_PROCESSING_ACCEL,
                vendor_id=analyzer.system_info.vendorid_ep,
                device_id=0x74A1,
            ),
        },
        other_pcie_cfg_space={
            _NIC_BDF: _cfg_with_class(_CLASS_NETWORK),
            "0000:03:00.0": _cfg_with_class(_CLASS_STORAGE),
        },
    )

    buckets = analyzer.bucket_devices(data)

    assert buckets["GPU"] == ["0000:01:00.0"]
    assert buckets["NIC"] == [_NIC_BDF]
    assert buckets["OTHER"] == ["0000:03:00.0"]


def test_nic_count_mismatch_logs_error(analyzer):
    """A NIC count differing from exp_nic_count raises an error event."""
    data = PcieDataModel(
        pcie_cfg_space={},
        other_pcie_cfg_space={_NIC_BDF: _cfg_with_class(_CLASS_NETWORK)},
    )
    args = PcieAnalyzerArgs(exp_nic_count=2)

    result = analyzer.analyze_data(data, args)

    assert _NIC_COUNT_MISMATCH in _descriptions(result)


def test_nic_count_match_logs_info(analyzer):
    """A NIC count equal to exp_nic_count logs a match and no mismatch."""
    data = PcieDataModel(
        pcie_cfg_space={},
        other_pcie_cfg_space={_NIC_BDF: _cfg_with_class(_CLASS_NETWORK)},
    )
    args = PcieAnalyzerArgs(exp_nic_count=1)

    result = analyzer.analyze_data(data, args)

    descriptions = _descriptions(result)
    assert _NIC_COUNT_MATCH in descriptions
    assert _NIC_COUNT_MISMATCH not in descriptions


def test_nic_count_not_checked_when_unset(analyzer):
    """With exp_nic_count unset, no NIC count event is produced."""
    data = PcieDataModel(
        pcie_cfg_space={},
        other_pcie_cfg_space={_NIC_BDF: _cfg_with_class(_CLASS_NETWORK)},
    )

    result = analyzer.analyze_data(data, PcieAnalyzerArgs())

    descriptions = _descriptions(result)
    assert _NIC_COUNT_MATCH not in descriptions
    assert _NIC_COUNT_MISMATCH not in descriptions


def test_nic_link_speed_mismatch_logs_error(analyzer):
    """A NIC negotiating below exp_nic_speed raises an unexpected-link-speed event."""
    data = PcieDataModel(
        pcie_cfg_space={},
        other_pcie_cfg_space={_NIC_BDF: _nic_cfg_with_link(_LNK_STAT_GEN4_X16, _LNK_CAP2_GENS_1_5)},
    )
    args = PcieAnalyzerArgs(exp_nic_speed=5)

    result = analyzer.analyze_data(data, args)

    speed_events = [
        e
        for e in result.events
        if e.description == _LINK_SPEED_ERR and e.data.get("bdf") == _NIC_BDF
    ]
    assert speed_events, "Expected an unexpected-link-speed event for the NIC"


def test_nic_link_speed_and_width_match_no_error(analyzer):
    """A NIC meeting exp_nic_speed and exp_nic_width produces no link error."""
    data = PcieDataModel(
        pcie_cfg_space={},
        other_pcie_cfg_space={_NIC_BDF: _nic_cfg_with_link(_LNK_STAT_GEN5_X16, _LNK_CAP2_GENS_1_5)},
    )
    args = PcieAnalyzerArgs(exp_nic_speed=5, exp_nic_width=16)

    result = analyzer.analyze_data(data, args)

    descriptions = _descriptions(result)
    assert _LINK_SPEED_ERR not in descriptions
    assert _LINK_WIDTH_ERR not in descriptions


_LNK_STAT_GEN6_X16 = (16 << 4) | 6
_LNK_STAT_LINK_DOWN = 0
# 0b111111 << 1 = gens 1-6.
_LNK_CAP2_GENS_1_6 = 0b111111 << 1

_NIC_CHECKS_SKIPPED = "NIC checks skipped: other PCI devices were not collected"
_NO_AMD_CFG = "No AMD PCIe config space found"
_NO_CFG = "No PCIe config space found"
_LINK_SPEED_ZERO = "Link speed vector is 0"
_LINK_EXCEPTION = "Exception occurred while checking link status"
_INVALID_INPUT = "User input for PcieAnalyzerModel is invalid"


def test_nic_checks_run_without_amd_devices(analyzer):
    """NIC checks still run when no AMD devices were collected. Uses the
    collector's real default of vf_pcie_cfg_space={}, not None."""
    data = PcieDataModel(
        pcie_cfg_space={},
        vf_pcie_cfg_space={},
        other_pcie_cfg_space={_NIC_BDF: _cfg_with_class(_CLASS_NETWORK)},
    )

    result = analyzer.analyze_data(data, PcieAnalyzerArgs(exp_nic_count=1))

    descriptions = _descriptions(result)
    assert _NO_AMD_CFG in descriptions
    assert _NIC_COUNT_MATCH in descriptions


def test_nothing_collected_returns_early(analyzer):
    """With no AMD and no other devices, the analyzer warns and stops."""
    data = PcieDataModel(pcie_cfg_space={}, vf_pcie_cfg_space={}, other_pcie_cfg_space=None)

    result = analyzer.analyze_data(data, PcieAnalyzerArgs(exp_nic_count=1))

    descriptions = _descriptions(result)
    assert _NO_CFG in descriptions
    assert _NIC_COUNT_MISMATCH not in descriptions


def test_nic_checks_skipped_when_other_devices_not_collected(analyzer):
    """exp_nic_count without collect_all_devices warns instead of reporting 0 NICs."""
    gpu = _cfg_with_class(
        _CLASS_PROCESSING_ACCEL, vendor_id=analyzer.system_info.vendorid_ep, device_id=0x74A1
    )
    data = PcieDataModel(pcie_cfg_space={"0000:01:00.0": gpu}, other_pcie_cfg_space=None)

    result = analyzer.analyze_data(data, PcieAnalyzerArgs(exp_nic_count=8))

    descriptions = _descriptions(result)
    assert _NIC_CHECKS_SKIPPED in descriptions
    assert _NIC_COUNT_MISMATCH not in descriptions


def test_nic_count_mismatch_when_collected_but_none_found(analyzer):
    """An empty (but collected) other_pcie_cfg_space is a real 0-NIC result."""
    data = PcieDataModel(pcie_cfg_space={}, vf_pcie_cfg_space={}, other_pcie_cfg_space={})
    gpu = _cfg_with_class(
        _CLASS_PROCESSING_ACCEL, vendor_id=analyzer.system_info.vendorid_ep, device_id=0x74A1
    )
    data.pcie_cfg_space["0000:01:00.0"] = gpu

    result = analyzer.analyze_data(data, PcieAnalyzerArgs(exp_nic_count=1))

    mismatch = [e for e in result.events if e.description == _NIC_COUNT_MISMATCH]
    assert mismatch and mismatch[0].data["nic_count"] == 0


def test_multi_port_nic_counted_once(analyzer):
    """Functions of the same NIC (same domain:bus:device) count as one NIC."""
    data = PcieDataModel(
        pcie_cfg_space={},
        other_pcie_cfg_space={
            "0000:02:00.0": _cfg_with_class(_CLASS_NETWORK),
            "0000:02:00.1": _cfg_with_class(_CLASS_NETWORK),
            "0000:03:00.0": _cfg_with_class(_CLASS_NETWORK),
        },
    )

    result = analyzer.analyze_data(data, PcieAnalyzerArgs(exp_nic_count=2))

    match = [e for e in result.events if e.description == _NIC_COUNT_MATCH]
    assert match
    assert match[0].data["nic_devices"] == ["0000:02:00", "0000:03:00"]


def test_gen6_nic_link_speed_supported(analyzer):
    """A Gen6 link is decoded instead of raising a KeyError."""
    data = PcieDataModel(
        pcie_cfg_space={},
        other_pcie_cfg_space={_NIC_BDF: _nic_cfg_with_link(_LNK_STAT_GEN6_X16, _LNK_CAP2_GENS_1_6)},
    )

    result = analyzer.analyze_data(data, PcieAnalyzerArgs(exp_nic_speed=6, exp_nic_width=16))

    descriptions = _descriptions(result)
    assert _INVALID_INPUT not in descriptions
    assert _LINK_EXCEPTION not in descriptions
    assert _LINK_SPEED_ERR not in descriptions
    assert _LINK_WIDTH_ERR not in descriptions


def test_width_only_check_does_not_report_speed(analyzer):
    """With only exp_nic_width set, a link-down NIC reports a width error, not a speed error."""
    data = PcieDataModel(
        pcie_cfg_space={},
        other_pcie_cfg_space={
            _NIC_BDF: _nic_cfg_with_link(_LNK_STAT_LINK_DOWN, _LNK_CAP2_GENS_1_6)
        },
    )

    result = analyzer.analyze_data(data, PcieAnalyzerArgs(exp_nic_width=16))

    descriptions = _descriptions(result)
    assert _LINK_SPEED_ZERO not in descriptions
    assert _LINK_WIDTH_ERR in descriptions


def test_invalid_nic_input_reported(analyzer):
    """An out-of-range NIC argument is named in the validation error event."""
    data = PcieDataModel(pcie_cfg_space={})

    result = analyzer.analyze_data(data, PcieAnalyzerArgs(exp_nic_width=32))

    invalid = [e for e in result.events if e.description == _INVALID_INPUT]
    assert invalid
    assert invalid[0].data["actual_input"]["exp_nic_width"] == 32


def test_other_devices_without_pcie_cap_are_skipped(analyzer):
    """Conventional PCI functions (e.g. host bridges) are not analyzed, so their
    status bits don't produce warnings, and missing AER caps aren't reported."""
    host_bridge = PcieCfgSpace()
    host_bridge.type_0_configuration.status.val = _STATUS_DET_PARITY_ERR
    data = PcieDataModel(
        pcie_cfg_space={},
        other_pcie_cfg_space={
            "0000:00:00.0": host_bridge,
            _OTHER_DEVICE_BDF: _clean_cfg_space(),
        },
    )

    result = analyzer.analyze_data(data, PcieAnalyzerArgs(analyze_other_devices=True))

    descriptions = _descriptions(result)
    assert _STATUS_ERR_DESC not in descriptions
    assert not any(d.startswith("Capability Structure") for d in descriptions)
    marker = [e for e in result.events if e.description == _ANALYZE_OTHER_DESC]
    assert marker[0].data["other_device_count"] == 1
    assert marker[0].data["skipped_non_pcie_device_count"] == 1


def test_nic_link_check_warns_when_no_nics(analyzer):
    """An expected NIC speed/width with no NICs found warns instead of passing silently."""
    data = PcieDataModel(
        pcie_cfg_space={},
        other_pcie_cfg_space={"0000:03:00.0": _cfg_with_class(_CLASS_STORAGE)},
    )

    result = analyzer.analyze_data(data, PcieAnalyzerArgs(exp_nic_speed=5))

    assert "NIC link check skipped: no NIC devices were collected" in _descriptions(result)


def test_nic_link_check_warns_on_nic_without_pcie_cap(analyzer):
    """NICs with no readable PCI Express capability (e.g. a 64-byte read without
    sudo) are reported instead of being skipped silently."""
    data = PcieDataModel(
        pcie_cfg_space={},
        other_pcie_cfg_space={
            _NIC_BDF: _cfg_with_class(_CLASS_NETWORK),
            "0000:03:00.0": _nic_cfg_with_link(_LNK_STAT_GEN5_X16, _LNK_CAP2_GENS_1_5),
        },
    )

    result = analyzer.analyze_data(data, PcieAnalyzerArgs(exp_nic_width=16))

    skipped = [
        e
        for e in result.events
        if e.description == "NIC link check skipped devices with no PCI Express capability"
    ]
    assert skipped and skipped[0].data["bdfs"] == [_NIC_BDF]
    assert _LINK_WIDTH_ERR not in _descriptions(result)


def test_amd_gpu_in_other_cfg_space_bucketed_as_gpu(analyzer):
    """An AMD GPU that was collected with the other devices (e.g. its GPU-path
    lookup failed) is still bucketed as a GPU, not as a NIC or OTHER."""
    gpu = _cfg_with_class(
        _CLASS_PROCESSING_ACCEL, vendor_id=analyzer.system_info.vendorid_ep, device_id=0x74A1
    )
    data = PcieDataModel(pcie_cfg_space={}, other_pcie_cfg_space={"0000:01:00.0": gpu})

    buckets = analyzer.bucket_devices(data)

    assert buckets["GPU"] == ["0000:01:00.0"]
    assert buckets["NIC"] == []
