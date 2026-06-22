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
"""Unit tests for amd-smi pydantic models (legacy JSON, ROCm 7.2+ / AMD-SMI 26.2+)."""

from typing import Any, Optional

import pytest

from nodescraper.plugins.inband.amdsmi.amdsmidata import (
    AmdSmiDataModel,
    AmdSmiMetric,
    MetricClockData,
    MetricPcie,
    MetricPower,
    StaticClockData,
    StaticFrequencyLevels,
    StaticLimit,
    ValueUnit,
)

DUMMY_STATIC_ASIC: dict[str, Any] = {
    "market_name": "AMD Instinct MI350X",
    "vendor_id": "0x1002",
    "vendor_name": "Advanced Micro Devices Inc. [AMD/ATI]",
    "subvendor_id": "0x1002",
    "device_id": "0x75a0",
    "subsystem_id": "0x75a0",
    "rev_id": "0x00",
    "asic_serial": "0xDUMMYASIC00000001",
    "oam_id": 6,
    "num_compute_units": 256,
    "target_graphics_version": "gfx950",
}

DUMMY_STATIC_BUS: dict[str, Any] = {
    "bdf": "0000:05:00.0",
    "max_pcie_width": 16,
    "max_pcie_speed": {"value": 32, "unit": "GT/s"},
    "pcie_interface_version": "Gen 5",
    "slot_type": "OAM",
}

DUMMY_STATIC_BOARD: dict[str, str] = {
    "model_number": "DUMMY-MI350X-OAM",
    "product_serial": "DUMMY-SN-000001",
    "fru_id": "DUMMY-FRU",
    "product_name": "AMD Instinct MI350X OAM",
    "manufacturer_name": "AMD",
}

DUMMY_STATIC_DRIVER: dict[str, Optional[str]] = {
    "driver_name": "amdgpu",
    "driver_version": "6.12.12",
    "os_kernel_version": "6.8.0-dummy",
}

DUMMY_STATIC_RAS: dict[str, Any] = {
    "eeprom_version": "N/A",
    "parity_schema": "DISABLED",
    "single_bit_schema": "ENABLED",
    "double_bit_schema": "ENABLED",
    "poison_schema": "ENABLED",
    "ecc_block_state": {},
}

DUMMY_STATIC_VRAM: dict[str, Any] = {
    "type": "HBM3",
    "vendor": "Micron",
    "size": {"value": 192, "unit": "GB"},
    "bit_width": {"value": 4096, "unit": "bit"},
}

DUMMY_LIMIT_LEGACY: dict[str, Any] = {
    "max_power": {"value": 550, "unit": "W"},
    "min_power": {"value": 0, "unit": "W"},
    "socket_power": {"value": 0, "unit": "W"},
}

DUMMY_LIMIT_PPT0: dict[str, Any] = {
    "ppt0": {
        "max_power_limit": {"value": 750, "unit": "W"},
        "min_power_limit": {"value": 0, "unit": "W"},
        "socket_power_limit": {"value": 600, "unit": "W"},
    },
    "ppt1": {
        "max_power_limit": "N/A",
        "min_power_limit": "N/A",
        "socket_power_limit": "N/A",
    },
}

DUMMY_CLOCK_LEGACY_FREQUENCY: dict[str, Any] = {
    "frequency": [500_000_000, 900_000_000, 1_300_000_000],
    "current": 0,
}

DUMMY_CLOCK_FREQUENCY_LEVELS: dict[str, Any] = {
    "GFX_0": {
        "frequency_levels": {
            "Level 0": {"value": 500, "unit": "MHz"},
            "Level 1": "900 MHz",
            "Level 2": "1300 MHz",
        },
        "current level": 0,
    }
}

DUMMY_METRIC_USAGE: dict[str, Any] = {
    "gfx_activity": {"value": 0, "unit": "%"},
    "umc_activity": {"value": 0, "unit": "%"},
    "mm_activity": "N/A",
    "vcn_activity": ["N/A", "N/A", "N/A", "N/A"],
    "jpeg_activity": ["N/A"] * 12,
    "gfx_busy_inst": None,
    "jpeg_busy": None,
    "vcn_busy": None,
}

DUMMY_METRIC_POWER: dict[str, Any] = {
    "socket_power": {"value": 140, "unit": "W"},
    "gfx_voltage": "N/A",
    "soc_voltage": "N/A",
    "mem_voltage": "N/A",
    "ubb_power": {"value": 1200, "unit": "W"},
    "throttle_status": "UNTHROTTLED",
    "power_management": "DISABLED",
}

DUMMY_METRIC_PCIE: dict[str, Any] = {
    "width": 16,
    "speed": {"value": 32, "unit": "GT/s"},
    "bandwidth": {"value": 512, "unit": "Gb/s"},
    "replay_count": 0,
    "l0_to_recovery_count": 0,
    "replay_roll_over_count": 0,
    "nak_sent_count": 0,
    "nak_received_count": 0,
    "current_bandwidth_sent": 0,
    "current_bandwidth_received": 0,
    "max_packet_size": 512,
    "lc_perf_other_end_recovery_count": 1,
}

DUMMY_METRIC_TEMPERATURE: dict[str, Any] = {
    "edge": "N/A",
    "hotspot": {"value": 37, "unit": "C"},
    "mem": {"value": 42, "unit": "C"},
}

DUMMY_METRIC_GPUBOARD: dict[str, Any] = {
    "temperature": {
        "NODE_RETIMER_X": 43,
        "NODE_OAM_X_IBC": 53,
    }
}

DUMMY_METRIC_BASEBOARD: dict[str, Any] = {
    "temperature": {
        "UBB_FRONT": 55,
        "UBB_FPGA": 78,
    }
}

_PCIE_KEYS = list(DUMMY_METRIC_PCIE.keys())


def _deep_update(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Shallow merge with one level of nested dict merge."""
    out = base.copy()
    for key, val in overrides.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            nested = out[key].copy()
            nested.update(val)
            out[key] = nested
        else:
            out[key] = val
    return out


def dummy_static_gpu_dict(
    *,
    gpu: int = 0,
    limit: Optional[dict[str, Any]] = None,
    clock: Optional[dict[str, Any]] = None,
    **overrides: Any,
) -> dict[str, Any]:
    """Build a minimal static GPU dict for ``AmdSmiStatic.model_validate``."""
    base: dict[str, Any] = {
        "gpu": gpu,
        "asic": dict(DUMMY_STATIC_ASIC),
        "bus": dict(DUMMY_STATIC_BUS),
        "driver": dict(DUMMY_STATIC_DRIVER),
        "board": dict(DUMMY_STATIC_BOARD),
        "ras": dict(DUMMY_STATIC_RAS),
        "process_isolation": "",
        "numa": {"node": 0, "affinity": 0},
        "vram": dict(DUMMY_STATIC_VRAM),
        "cache_info": [],
        "limit": limit,
        "clock": clock,
    }
    return _deep_update(base, overrides)


def dummy_metric_dict(
    *,
    gpu: int = 0,
    usage: Any = None,
    power: Optional[dict[str, Any]] = None,
    pcie: Optional[dict[str, Any]] = None,
    **overrides: Any,
) -> dict[str, Any]:
    """Build a minimal metric GPU dict for ``AmdSmiMetric.model_validate``."""
    base: dict[str, Any] = {
        "gpu": gpu,
        "usage": DUMMY_METRIC_USAGE if usage is None else usage,
        "power": dict(DUMMY_METRIC_POWER) if power is None else power,
        "clock": {
            "GFX_0": {
                "clk": {"value": 132, "unit": "MHz"},
                "min_clk": {"value": 500, "unit": "MHz"},
                "max_clk": {"value": 2100, "unit": "MHz"},
            }
        },
        "temperature": dict(DUMMY_METRIC_TEMPERATURE),
        "pcie": dict(DUMMY_METRIC_PCIE) if pcie is None else pcie,
        "ecc": {
            "total_correctable_count": 0,
            "total_uncorrectable_count": 0,
            "total_deferred_count": 0,
            "cache_correctable_count": 0,
            "cache_uncorrectable_count": 0,
        },
        "ecc_blocks": {},
        "fan": {"speed": "N/A", "max": "N/A", "rpm": "N/A", "usage": "N/A"},
        "voltage_curve": None,
        "perf_level": "auto",
        "xgmi_err": "N/A",
        "energy": None,
        "mem_usage": {
            "total_vram": {"value": 192, "unit": "GB"},
            "used_vram": {"value": 0, "unit": "GB"},
            "free_vram": {"value": 192, "unit": "GB"},
            "total_visible_vram": None,
            "used_visible_vram": None,
            "free_visible_vram": None,
            "total_gtt": None,
            "used_gtt": None,
            "free_gtt": None,
        },
        "throttle": {},
        "gpuboard": dict(DUMMY_METRIC_GPUBOARD),
        "baseboard": dict(DUMMY_METRIC_BASEBOARD),
    }
    return _deep_update(base, overrides)


def dummy_amdsmi_data_dict(
    *,
    static: Optional[list[dict[str, Any]]] = None,
    metric: Optional[list[dict[str, Any]]] = None,
    **overrides: Any,
) -> dict[str, Any]:
    """Build top-level ``AmdSmiDataModel`` input with dummy static + metric lists."""
    base: dict[str, Any] = {
        "static": (
            static
            if static is not None
            else [
                dummy_static_gpu_dict(
                    limit=dict(DUMMY_LIMIT_PPT0), clock=dict(DUMMY_CLOCK_FREQUENCY_LEVELS)
                ),
            ]
        ),
        "metric": metric if metric is not None else [dummy_metric_dict(gpu=0)],
    }
    return _deep_update(base, overrides)


def _pcie_dict(**overrides: Any) -> MetricPcie:
    """Full PCIe model from dummy defaults plus overrides."""
    base = dict(DUMMY_METRIC_PCIE)
    base.update(overrides)
    for key, val in list(base.items()):
        if isinstance(val, ValueUnit):
            base[key] = {"value": val.value, "unit": val.unit}
    return MetricPcie.model_validate(base)


@pytest.mark.parametrize(
    "level_input,expected_value,expected_unit",
    [
        ("138 MHz", 138, "MHz"),
        ({"value": 500, "unit": "MHz"}, 500, "MHz"),
        (900, 900, ""),
        (ValueUnit(value=1300, unit="MHz"), 1300, "MHz"),
    ],
)
def test_static_frequency_levels_coerce_to_value_unit(level_input, expected_value, expected_unit):
    """Static frequency levels accept strings, dicts, numbers, and ValueUnit."""
    levels = StaticFrequencyLevels.model_validate(
        {"Level 0": level_input, "Level 1": None, "Level 2": None}
    )
    assert isinstance(levels.Level_0, ValueUnit)
    assert levels.Level_0.value == expected_value
    assert levels.Level_0.unit == expected_unit
    assert levels.Level_1 is None
    assert levels.Level_2 is None


def test_static_frequency_levels_optional_levels():
    """Level 1/2 coerce from amd-smi string and structured JSON forms."""
    levels = StaticFrequencyLevels.model_validate(
        DUMMY_CLOCK_FREQUENCY_LEVELS["GFX_0"]["frequency_levels"]
    )
    assert levels.Level_0.value == 500
    assert levels.Level_1 is not None and levels.Level_1.value == 900
    assert levels.Level_2 is not None and levels.Level_2.value == 1300


def test_static_frequency_levels_accepts_level_three_plus():
    """ROCm 7.2+ / AMD-SMI 26.2+ may expose additional DPM levels (e.g. Level 3)."""
    levels = StaticFrequencyLevels.model_validate(
        {
            "Level 0": "400 MHz",
            "Level 1": "800 MHz",
            "Level 2": "1000 MHz",
            "Level 3": "1143 MHz",
        }
    )
    assert levels.Level_3 is not None
    assert levels.Level_3.value == 1143
    assert levels.Level_3.unit == "MHz"


def test_static_frequency_levels_legacy_amd_smi_three_levels_only():
    """Legacy static JSON: only Level 0–2 (no Level 3+ keys)."""
    levels = StaticFrequencyLevels.model_validate(
        {
            "Level 0": {"value": 500, "unit": "MHz"},
            "Level 1": "900 MHz",
            "Level 2": "1300 MHz",
        }
    )
    assert levels.Level_0.value == 500
    assert levels.Level_2 is not None and levels.Level_2.value == 1300
    assert levels.Level_3 is None
    assert levels.Level_15 is None


def test_static_limit_legacy_max_power():
    """Legacy flat max_power field still resolves."""
    limit = StaticLimit.model_validate(DUMMY_LIMIT_LEGACY)
    resolved = limit.resolved_max_power()
    assert resolved is not None
    assert resolved.value == 550


def test_static_limit_ppt0_max_power():
    """ROCm 7+ ppt0.max_power_limit resolves when flat max_power is absent."""
    limit = StaticLimit.model_validate(DUMMY_LIMIT_PPT0)
    assert limit.max_power is None
    resolved = limit.resolved_max_power()
    assert resolved is not None
    assert resolved.value == 750


def test_ref_max_power_w_prefers_ppt0_when_legacy_missing():
    """Reference snapshot uses ppt0 on newer static JSON."""
    data = AmdSmiDataModel.model_validate(
        dummy_amdsmi_data_dict(
            static=[dummy_static_gpu_dict(limit=dict(DUMMY_LIMIT_PPT0))],
        )
    )
    assert data.ref_max_power_w == 750


def test_ref_max_power_w_legacy_limit():
    """Reference snapshot uses legacy max_power when present."""
    data = AmdSmiDataModel.model_validate(
        dummy_amdsmi_data_dict(
            static=[dummy_static_gpu_dict(limit=dict(DUMMY_LIMIT_LEGACY))],
        )
    )
    assert data.ref_max_power_w == 550


def test_static_clock_frequency_levels_json():
    """Static clock accepts ROCm 7+ frequency_levels object."""
    clock = StaticClockData.model_validate(
        {
            "frequency_levels": DUMMY_CLOCK_FREQUENCY_LEVELS["GFX_0"]["frequency_levels"],
            "current level": 0,
        }
    )
    assert clock.frequency_levels.Level_0.value == 500
    assert clock.frequency_levels.Level_1 is not None
    assert clock.frequency_levels.Level_1.value == 900


def test_amdsmi_data_model_dummy_metric_round_trip():
    """Full dummy metric payload validates and preserves key ROCm 7.13 fields."""
    metric = AmdSmiMetric.model_validate(dummy_metric_dict())
    assert metric.gpu == 0
    assert metric.power.power_management == "DISABLED"
    assert metric.power.ubb_power is not None
    assert metric.power.ubb_power.value == 1200
    assert metric.pcie.width == 16
    assert metric.pcie.lc_perf_other_end_recovery_count == 1
    assert metric.gpuboard is not None
    assert metric.baseboard is not None


def test_metric_pcie_lc_perf_alias():
    """Metric PCIe accepts legacy lc_perf_other_end_recovery JSON key."""
    pcie = _pcie_dict(lc_perf_other_end_recovery=2)
    assert pcie.lc_perf_other_end_recovery_count == 2
    assert pcie.lc_perf_other_end_recovery == 2


def test_metric_pcie_lc_perf_count_key():
    """Metric PCIe accepts renamed lc_perf_other_end_recovery_count key."""
    pcie = _pcie_dict(lc_perf_other_end_recovery_count=3)
    assert pcie.lc_perf_other_end_recovery_count == 3
    assert pcie.lc_perf_other_end_recovery == 3


def test_metric_legacy_mi300_shape():
    """Legacy metric JSON without MI355-only clock/board fields still validates."""
    pcie_legacy = {
        k: v for k, v in DUMMY_METRIC_PCIE.items() if k != "lc_perf_other_end_recovery_count"
    }
    pcie_legacy["lc_perf_other_end_recovery"] = 1
    metric = AmdSmiMetric.model_validate(
        dummy_metric_dict(
            pcie=pcie_legacy,
            gpuboard=None,
            baseboard=None,
        )
    )
    assert metric.gpuboard is None
    assert metric.baseboard is None
    assert isinstance(metric.clock["GFX_0"], MetricClockData)
    assert metric.clock["GFX_0"].clk is not None
    assert metric.pcie.lc_perf_other_end_recovery_count == 1
    assert metric.pcie.lc_perf_other_end_recovery == 1


def test_metric_power_ubb_coercion():
    """Metric power accepts ubb_power as string or ValueUnit."""
    power = MetricPower.model_validate(
        {
            **DUMMY_METRIC_POWER,
            "ubb_power": "1200 W",
        }
    )
    assert power.ubb_power is not None
    assert power.ubb_power.value == 1200
    assert power.ubb_power.unit == "W"


def test_metric_usage_string_na():
    """Whole usage block may be N/A on some platforms."""
    metric = AmdSmiMetric.model_validate(dummy_metric_dict(usage="N/A"))
    assert metric.usage == "N/A"


def test_metric_gpuboard_baseboard_optional():
    """Store gpuboard/baseboard sections from ROCm 7.1+ metric output."""
    metric = AmdSmiMetric.model_validate(
        dummy_metric_dict(
            gpuboard=DUMMY_METRIC_GPUBOARD,
            baseboard=DUMMY_METRIC_BASEBOARD,
        )
    )
    assert metric.gpuboard == DUMMY_METRIC_GPUBOARD
    assert metric.baseboard == DUMMY_METRIC_BASEBOARD


def test_metric_gpuboard_gpu_board_alias():
    """amd-smi may emit gpu_board / base_board instead of gpuboard / baseboard."""
    metric = AmdSmiMetric.model_validate(
        dummy_metric_dict(
            **{
                "gpu_board": DUMMY_METRIC_GPUBOARD,
                "base_board": DUMMY_METRIC_BASEBOARD,
            }
        )
    )
    assert metric.gpuboard == DUMMY_METRIC_GPUBOARD
    assert metric.baseboard == DUMMY_METRIC_BASEBOARD


def test_metric_clock_per_aid_na_maps():
    """MI355 metric clock may expose per-AID/MID maps instead of MetricClockData leaves."""
    metric = AmdSmiMetric.model_validate(
        dummy_metric_dict(
            clock={
                "GFX_0": {
                    "clk": {"value": 132, "unit": "MHz"},
                    "min_clk": {"value": 500, "unit": "MHz"},
                    "max_clk": {"value": 2100, "unit": "MHz"},
                    "clk_locked": 0,
                    "deep_sleep": 0,
                },
                "uclk_aid": {"AID_0": "N/A", "AID_1": "N/A"},
                "socclks_mid": {"MID_0": "N/A", "MID_1": "N/A"},
            },
            pcie={
                **DUMMY_METRIC_PCIE,
                "current_bandwidth_sent": "N/A",
                "current_bandwidth_received": "N/A",
                "max_packet_size": "N/A",
                "lc_perf_other_end_recovery_count": 0,
            },
        )
    )
    assert isinstance(metric.clock["uclk_aid"], dict)
    assert metric.clock["uclk_aid"]["AID_0"] == "N/A"
    assert isinstance(metric.clock["GFX_0"], MetricClockData)
    assert metric.pcie.lc_perf_other_end_recovery_count == 0
