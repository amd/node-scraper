"""Host-driver (mxGPU) Pydantic models for amd-smi data.

The mxGPU host driver ships an amd-smi build whose JSON schema differs from the
guest amdgpu build. The same host schema is used by both `gim` (Linux host) and
`amdgpuv` (ESXi host), so these models serve both; the base AmdSmi* models serve
the guest amdgpu build.
"""

from __future__ import annotations

from typing import Any

from pydantic import (
    AliasPath,
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
)

from nodescraper.plugins.inband.amdsmi.amdsmidata import (
    AmdSmiBaseModel,
    EccData,
    EccState,
    ValueUnit,
)


def _host_na_to_none(value: Any) -> Any:
    """Convert amd-smi N/A markers to None.

    Newer amd-smi (e.g. 37.0.5) emits N/A both as a scalar ("N/A") and as a
    ``{"value": "N/A", "unit": "N/A"}`` dict for ValueUnit fields; the base
    ValueUnit coercion does not collapse the dict form inside a ``ValueUnit | None``
    union, so normalize both to None before field validation.
    """
    if isinstance(value, str) and value.strip().upper() in ("N/A", "NA", ""):
        return None
    if isinstance(value, dict):
        inner = value.get("value")
        if isinstance(inner, str) and inner.strip().upper() in ("N/A", "NA", ""):
            return None
    return value


class HostDriverAmdSmiVersion(BaseModel):
    """mxGPU host `amd-smi version --json` nests its fields under a top-level
    "version" key: ``{"version": {"tool_name": ..., "tool_version": ...}}``.

    AliasPath reads each field from that nested dict, so the collector can build
    this model directly from the raw item - no unwrapping needed. (Guest/bare-metal
    amdgpu instead put a scalar "version" string in a flat dict; that is the
    separate AmdSmiVersion model.)
    """

    tool_name: str | None = Field(default=None, validation_alias=AliasPath("version", "tool_name"))
    tool_version: str | None = Field(
        default=None, validation_alias=AliasPath("version", "tool_version")
    )
    lib_version: str | None = Field(
        default=None, validation_alias=AliasPath("version", "lib_version")
    )
    driver_version: str | None = Field(
        default=None, validation_alias=AliasPath("version", "driver_version")
    )
    # mxGPU host amd-smi does not report a ROCm version; kept here (always None) so
    # version consumers - e.g. the amdsmitst ROCm-version gate - can read it uniformly.
    rocm_version: str | None = None


class HostDriverAmdSmiListItem(BaseModel):
    """mxGPU host amd-smi list has gpu/bdf/uuid/vfs — no kfd_id/node_id/partition_id."""

    model_config = ConfigDict(extra="ignore")

    gpu: int
    bdf: str
    uuid: str


class HostDriverStaticAsic(BaseModel):
    # Expose num_compute_units (matching the guest model + AmdSmiAnalyzer) while
    # accepting the host driver's JSON key "num_of_compute_units" via alias.
    model_config = ConfigDict(populate_by_name=True)

    market_name: str
    vendor_id: str
    vendor_name: str
    subvendor_id: str
    device_id: str
    subsystem_id: str
    rev_id: str
    asic_serial: str
    oam_id: int | str
    num_compute_units: int | str = Field(alias="num_of_compute_units")
    # Host driver amd-smi does not report target_graphics_version; keep optional
    # so AmdSmiAnalyzer.static_consistancy_check can read it uniformly.
    target_graphics_version: str | None = None


class HostDriverStaticIfwi(BaseModel):
    name: str
    build_date: str
    part_number: str
    version: str
    boot_firmware: str | None = None


class HostDriverStaticBus(AmdSmiBaseModel):
    bdf: str
    max_pcie_width: ValueUnit
    max_pcie_speed: ValueUnit
    pcie_interface_version: str
    slot_type: str
    max_pcie_interface_version: str | None = None


class HostDriverStaticPpt(AmdSmiBaseModel):
    """Host per-PPT power caps (amd-smi 37.0.5+ nests these under limit.ppt0/ppt1).

    The host build keys these ``max_power``/``min_power``/``socket_power`` — unlike
    the base ``StaticPowerLimit`` (guest/bare-metal ROCm 7+) which uses the
    ``*_power_limit`` key names.
    """

    model_config = ConfigDict(extra="ignore")

    max_power: ValueUnit | None = None
    min_power: ValueUnit | None = None
    socket_power: ValueUnit | None = None
    na_validator = field_validator(
        "max_power",
        "min_power",
        "socket_power",
        mode="before",
    )(_host_na_to_none)


class HostDriverStaticLimit(AmdSmiBaseModel):
    # Host amd-smi adds per-partition power fields (ppt0/ppt1, ...) across tool
    # versions; ignore unknown fields so a new field doesn't drop all static data.
    model_config = ConfigDict(extra="ignore")

    max_power: ValueUnit | None = None
    min_power: ValueUnit | None = None
    socket_power: ValueUnit | None = None
    slowdown_edge_temperature: ValueUnit | None = None
    slowdown_hotspot_temperature: ValueUnit | None = None
    slowdown_mem_temperature: ValueUnit | None = None
    shutdown_edge_temperature: ValueUnit | None = None
    shutdown_hotspot_temperature: ValueUnit | None = None
    shutdown_mem_temperature: ValueUnit | None = None
    # amd-smi 37.0.5 moved the flat max/min/socket power caps under ppt0 (active
    # profile) / ppt1 (secondary, often N/A); older builds used the flat fields.
    ppt0: HostDriverStaticPpt | None = None
    ppt1: HostDriverStaticPpt | None = None
    na_validator = field_validator(
        "max_power",
        "min_power",
        "socket_power",
        "slowdown_edge_temperature",
        "slowdown_hotspot_temperature",
        "slowdown_mem_temperature",
        "shutdown_edge_temperature",
        "shutdown_hotspot_temperature",
        "shutdown_mem_temperature",
        "ppt0",
        "ppt1",
        mode="before",
    )(_host_na_to_none)

    def resolved_max_power(self) -> ValueUnit | None:
        """Match the base StaticLimit contract so the shared analyzer / data-model
        max-power helpers work on host data. Older host builds expose a flat
        max_power; amd-smi 37.0.5 moved it under limit.ppt0."""
        if self.max_power is not None:
            return self.max_power
        if self.ppt0 is not None and self.ppt0.max_power is not None:
            return self.ppt0.max_power
        return None


class HostDriverStaticDriver(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    version: str
    date: str | None = None
    model: str | None = None


class HostDriverStaticBoard(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # "model_" is a pydantic-reserved namespace; expose as amdsmi_model_number
    # (matching the base StaticBoard) while reading the JSON "model_number" key.
    amdsmi_model_number: str = Field(alias="model_number")
    product_serial: str
    fru_id: str
    product_name: str
    manufacturer_name: str


class HostDriverStaticRas(BaseModel):
    model_config = ConfigDict(extra="ignore")

    eeprom_version: str
    parity_schema: EccState
    single_bit_schema: EccState
    double_bit_schema: EccState
    poison_schema: EccState
    block_state: dict[str, EccState] | str


class HostDriverStaticFbInfo(AmdSmiBaseModel):
    total_fb_size: ValueUnit | None = None
    pf_fb_reserved: ValueUnit | None = None
    pf_fb_offset: ValueUnit | None = None
    fb_alignment: ValueUnit | None = None
    max_vf_fb_usable: ValueUnit | None = None
    min_vf_fb_usable: ValueUnit | None = None


class HostDriverStaticNumVf(BaseModel):
    supported: int
    enabled: int


class HostDriverStaticVram(AmdSmiBaseModel):
    type: str
    vendor: str | None = None
    size: ValueUnit | None = None
    bit_width: ValueUnit | int | None = None
    max_bandwidth: ValueUnit | None = None
    na_validator = field_validator("vendor", "size", "bit_width", "max_bandwidth", mode="before")(
        _host_na_to_none
    )


class HostDriverStaticNuma(BaseModel):
    # gim (Linux mxGPU host) reports cpu_affinity as a dict ({"cpu_list": [...]});
    # amdgpuv (ESXi mxGPU host) reports it as int/str. Accept both.
    node: int | str | dict | None = None
    cpu_affinity: int | str | dict | None = None
    socket_affinity: int | str | dict | None = None
    na_validator = field_validator("node", "cpu_affinity", "socket_affinity", mode="before")(
        _host_na_to_none
    )


class HostDriverStaticPartition(BaseModel):
    model_config = ConfigDict(extra="ignore")

    accelerator_partition: str
    memory_partition: str
    partition_id: list[int] | int


class HostDriverStaticXgmiPlpd(BaseModel):
    num_supported: int
    current_id: int
    policies: list[dict] = Field(default_factory=list)


class HostDriverAmdSmiStatic(BaseModel):
    """mxGPU host static model — uses ifwi instead of vbios, has fb_info/num-vf, etc."""

    model_config = ConfigDict(extra="ignore")

    gpu: int
    asic: HostDriverStaticAsic
    bus: HostDriverStaticBus
    ifwi: HostDriverStaticIfwi | None = None
    limit: HostDriverStaticLimit | None = None
    driver: HostDriverStaticDriver
    board: HostDriverStaticBoard
    ras: HostDriverStaticRas
    fb_info: HostDriverStaticFbInfo | None = None
    num_vf: HostDriverStaticNumVf | None = Field(default=None, alias="num-vf")
    vram: HostDriverStaticVram
    cache_info: list[dict] = Field(default_factory=list)
    xgmi_plpd: HostDriverStaticXgmiPlpd | None = Field(default=None, alias="xgmi-plpd")
    partition: HostDriverStaticPartition | None = None
    numa: HostDriverStaticNuma
    na_validator = field_validator("limit", "ifwi", "xgmi_plpd", mode="before")(_host_na_to_none)


# --- Metric models ---


class HostDriverMetricUsage(BaseModel):
    gfx_activity: ValueUnit | None = None
    umc_activity: ValueUnit | None = None
    mm_activity: ValueUnit | None = None
    vcn_activity: list[ValueUnit | str | None] = Field(default_factory=list)
    jpeg_activity: list[ValueUnit | str | None] = Field(default_factory=list)
    na_validator = field_validator("gfx_activity", "umc_activity", "mm_activity", mode="before")(
        _host_na_to_none
    )


class HostDriverMetricPower(BaseModel):
    socket_power: ValueUnit | None = None
    gfx_voltage: ValueUnit | None = None
    soc_voltage: ValueUnit | None = None
    mem_voltage: ValueUnit | None = None
    power_management: str | None = None
    na_validator = field_validator(
        "socket_power",
        "gfx_voltage",
        "soc_voltage",
        "mem_voltage",
        "power_management",
        mode="before",
    )(_host_na_to_none)


class HostDriverMetricClockData(BaseModel):
    clk: ValueUnit | None = None
    min_clk: ValueUnit | None = None
    max_clk: ValueUnit | None = None
    clk_locked: int | str | dict | None = None
    deep_sleep: int | str | dict | None = None
    na_validator = field_validator(
        "clk", "min_clk", "max_clk", "clk_locked", "deep_sleep", mode="before"
    )(_host_na_to_none)


class HostDriverMetricTemperature(BaseModel):
    edge: ValueUnit | None = None
    hotspot: ValueUnit | None = None
    mem: ValueUnit | None = None
    na_validator = field_validator("edge", "hotspot", "mem", mode="before")(_host_na_to_none)


class HostDriverMetricPcie(BaseModel):
    width: int | None = None
    speed: ValueUnit | None = None
    bandwidth: ValueUnit | None = None
    replay_count: int | None = None
    l0_to_recovery_count: int | None = None
    replay_roll_over_count: int | None = None
    nak_sent_count: int | None = None
    nak_received_count: int | None = None
    na_validator = field_validator(
        "width",
        "speed",
        "bandwidth",
        "replay_count",
        "l0_to_recovery_count",
        "replay_roll_over_count",
        "nak_sent_count",
        "nak_received_count",
        mode="before",
    )(_host_na_to_none)


class HostDriverMetricEccTotals(BaseModel):
    total_correctable_count: int | None = None
    total_uncorrectable_count: int | None = None
    total_deferred_count: int | None = None
    cache_correctable_count: int | None = None
    cache_uncorrectable_count: int | None = None
    na_validator = field_validator(
        "total_correctable_count",
        "total_uncorrectable_count",
        "total_deferred_count",
        "cache_correctable_count",
        "cache_uncorrectable_count",
        mode="before",
    )(_host_na_to_none)


class HostDriverMetricEnergy(BaseModel):
    total_energy_consumption: ValueUnit | None = None
    na_validator = field_validator("total_energy_consumption", mode="before")(_host_na_to_none)


class HostDriverMetricGpuBoard(BaseModel):
    model_config = ConfigDict(extra="allow")


class HostDriverAmdSmiMetric(BaseModel):
    """mxGPU host metric model — no fan/voltage_curve/perf_level/xgmi_err/mem_usage/throttle,
    has gpuboard instead."""

    model_config = ConfigDict(extra="ignore")

    gpu: int
    usage: HostDriverMetricUsage | str
    power: HostDriverMetricPower
    clock: dict[str, HostDriverMetricClockData | dict]
    temperature: HostDriverMetricTemperature
    pcie: HostDriverMetricPcie
    ecc: HostDriverMetricEccTotals
    ecc_blocks: dict[str, EccData] | str = Field(default_factory=dict)
    energy: HostDriverMetricEnergy | None = None
    gpuboard: HostDriverMetricGpuBoard | None = None

    @field_validator("ecc_blocks", mode="before")
    @classmethod
    def validate_ecc_blocks(cls, value):
        if isinstance(value, str):
            return {}
        return value

    @field_validator("energy", mode="before")
    @classmethod
    def validate_energy(cls, value):
        if value == "N/A" or value is None:
            return None
        return value


# --- Topology ---


class HostDriverTopoLink(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    gpu: int
    bdf: str
    weight: int
    link_type: str
    num_hops: int
    bandwidth: str = ""
    fb_sharing: str | None = None
    coherent: str | None = None
    atomics: str | None = None
    dma: str | None = None
    bi_dir: str | None = Field(default=None, alias="bi-dir")

    @computed_field
    def bandwidth_from(self) -> int | None:
        bw_split = self.bandwidth.split("-")
        return int(bw_split[0]) if len(bw_split) == 2 else None

    @computed_field
    def bandwidth_to(self) -> int | None:
        bw_split = self.bandwidth.split("-")
        return int(bw_split[1]) if len(bw_split) == 2 else None


class HostDriverTopo(BaseModel):
    gpu: int
    bdf: str
    links: list[HostDriverTopoLink]


# --- Bad pages ---


class HostDriverBadPageEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    bad_page: int
    retired_bad_page: str
    timestamp: str | None = None
    mem_channel: int | None = None
    mcumc_id: int | None = None


class HostDriverBadPages(BaseModel):
    gpu: int
    bad_pages: list[HostDriverBadPageEntry] = Field(default_factory=list)


# --- XGMI ---


class HostDriverXgmiLink(BaseModel):
    gpu: int
    bdf: str
    read: ValueUnit | None = None
    write: ValueUnit | None = None
    na_validator = field_validator("read", "write", mode="before")(_host_na_to_none)


class HostDriverXgmiLinkMetrics(BaseModel):
    bit_rate: ValueUnit | None = None
    max_bandwidth: ValueUnit | None = None
    links: list[HostDriverXgmiLink] = Field(default_factory=list)
    na_validator = field_validator("max_bandwidth", "bit_rate", mode="before")(_host_na_to_none)


class HostDriverXgmiMetrics(BaseModel):
    gpu: int
    bdf: str
    link_metrics: HostDriverXgmiLinkMetrics


class HostDriverXgmiLinkStatus(BaseModel):
    gpu: int
    bdf: str
    status: str


class HostDriverXgmiLinks(BaseModel):
    gpu: int
    bdf: str
    link_status: list[HostDriverXgmiLinkStatus]
