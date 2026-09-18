"""Guest-VF (virtualized amdgpu) Pydantic models for amd-smi data.

A guest VM sees a single amdgpu virtual function (VF). Its amd-smi build shares
the bare-metal amdgpu JSON schema EXCEPT that a VF does not expose physical /
host-owned fields: fan control, SoC power state, power/thermal limits, NUMA
topology, XGMI power-down policy, and energy/throttle/voltage-curve/perf-level
counters. The bare-metal ``AmdSmi*`` models mark those fields as required, so a
guest payload fails to build against them; these subclasses relax exactly those
fields to optional and inherit all other structure unchanged.

amd-smi was not exercised on the guest before the host/guest driver-flavor work,
so the base ``AmdSmi*`` models had implicitly assumed bare-metal amdgpu.
"""

from __future__ import annotations

from pydantic import ConfigDict

from nodescraper.plugins.inband.amdsmi.amdsmidata import (
    AmdSmiMetric,
    AmdSmiStatic,
    MetricEnergy,
    MetricFan,
    MetricMemUsage,
    MetricThrottle,
    MetricVoltageCurve,
    StaticBus,
    StaticLimit,
    StaticNuma,
    StaticSocPstate,
    StaticVbios,
    StaticXgmiPlpd,
)


class GuestStaticBus(StaticBus):
    """Guest amd-smi (ROCm 7.14+) adds a per-link ``pcie_levels`` block to the bus
    section that the base ``StaticBus`` (``extra="forbid"``) rejects. Ignore unknown
    bus fields so a new field doesn't drop the whole static payload, matching the
    host models' schema-drift resilience."""

    model_config = ConfigDict(extra="ignore")


class GuestAmdSmiStatic(AmdSmiStatic):
    """Bare-metal static schema minus the physical fields a guest VF omits."""

    # Base bus (StaticBus) forbids extras; the guest build adds pcie_levels.
    bus: GuestStaticBus  # type: ignore[assignment]
    soc_pstate: StaticSocPstate | None = None
    xgmi_plpd: StaticXgmiPlpd | None = None
    numa: StaticNuma | None = None  # type: ignore[assignment]
    limit: StaticLimit | None = None
    # A guest VF's static payload carries an ``ifwi`` firmware block (name,
    # build_date, part_number, version) that the bare-metal schema omits; its
    # shape matches StaticVbios.
    ifwi: StaticVbios | None = None


class GuestAmdSmiMetric(AmdSmiMetric):
    """Bare-metal metric schema minus the physical fields a guest VF omits."""

    # These physical fields are required on the bare-metal base model; a guest VF
    # omits them, so relax to Optional (intentional LSP-widening override).
    fan: MetricFan | None = None  # type: ignore[assignment]
    voltage_curve: MetricVoltageCurve | None = None
    perf_level: str | dict | None = None
    xgmi_err: str | dict | None = None
    energy: MetricEnergy | None = None
    throttle: MetricThrottle | None = None  # type: ignore[assignment]
    mem_usage: MetricMemUsage | None = None  # type: ignore[assignment]
