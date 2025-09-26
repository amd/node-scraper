import re
from typing import Any, List, Mapping

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from nodescraper.models.datamodel import DataModel
from nodescraper.utils import find_annotation_in_container

_NUM_UNIT_RE = re.compile(r"^\s*([-+]?\d+(?:\.\d+)?)(?:\s*([A-Za-z%/][A-Za-z0-9%/._-]*))?\s*$")


def na_to_none(values: int | str):
    if values == "N/A":
        return None
    return values


def na_to_none_list(values: List[int | str | None]) -> List[int | str | None]:
    ret_list: List[int | str | None] = values.copy()
    for i in range(len(ret_list)):
        if ret_list[i] == "N/A":
            ret_list[i] = None
    return ret_list


def na_to_none_dict(values: object) -> dict[str, Any] | None:
    """Normalize mapping-like fields where 'N/A' or empty should become None.
    Accepts None; returns None for 'N/A'/'NA'/'' or non-mapping inputs."""
    if values is None:
        return None
    if isinstance(values, str) and values.strip().upper() in {"N/A", "NA", ""}:
        return None
    if not isinstance(values, Mapping):
        return None

    out: dict[str, Any] = {}
    for k, v in values.items():
        if isinstance(v, str) and v.strip().upper() in {"N/A", "NA", ""}:
            out[k] = None
        else:
            out[k] = v
    return out


class AmdSmiBaseModel(BaseModel):
    """Base model for AMD SMI data models.

    This is used to ensure that all AMD SMI data models have the same
    configuration and validation.
    """

    model_config = ConfigDict(
        str_min_length=1,
        str_strip_whitespace=True,
        populate_by_name=True,
        extra="forbid",  # Forbid extra fields not defined in the model
    )

    # During building if a field contains a ValueUnit in its tuple, convert input into a ValueUnit
    def __init__(self, **data):
        # Convert all fields that are supposed to be ValueUnit to ValueUnit if they are int | str | float
        for field_name, field_type in self.model_fields.items():
            annotation = field_type.annotation
            target_type, container = find_annotation_in_container(annotation, ValueUnit)
            if target_type is None:
                continue

            if field_name in data and isinstance(data[field_name], (int, str, float)):
                # If the field is a primitive type, convert it to ValueUnit dict and let validtor handle it
                data[field_name] = {
                    "value": data[field_name],
                    "unit": "",
                }

        super().__init__(**data)


class ValueUnit(BaseModel):
    """A model for a value with a unit.

    Accepts:
      - dict: {"value": 123, "unit": "W"}
      - number: 123  -> unit=""
      - string with number+unit: "123 W" -> {"value": 123, "unit": "W"}
      - "N/A" / "NA" / "" / None -> None
    """

    value: int | float | str
    unit: str = ""

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, v):
        # treat N/A as None
        def na(x) -> bool:
            return x is None or (isinstance(x, str) and x.strip().upper() in {"N/A", "NA", ""})

        if na(v):
            return None

        # Dict form: normalize value and possibly extract unit
        if isinstance(v, dict):
            val = v.get("value")
            unit = v.get("unit", "")
            if na(val):
                return None
            if isinstance(val, str):
                m = _NUM_UNIT_RE.match(val.strip())
                if m and not unit:
                    num, u = m.groups()
                    unit = u or unit or ""
                    val = float(num) if "." in num else int(num)
            return {"value": val, "unit": unit}

        # numbers
        if isinstance(v, (int, float)):
            return {"value": v, "unit": ""}

        if isinstance(v, str):
            s = v.strip()
            m = _NUM_UNIT_RE.match(s)
            if m:
                num, unit = m.groups()
                val = float(num) if "." in num else int(num)
                return {"value": val, "unit": unit or ""}
            return {"value": s, "unit": ""}

        return v

    @field_validator("unit")
    @classmethod
    def _clean_unit(cls, u):
        return "" if u is None else str(u).strip()


# Process
class ProcessMemoryUsage(BaseModel):
    gtt_mem: ValueUnit | None
    cpu_mem: ValueUnit | None
    vram_mem: ValueUnit | None

    na_validator = field_validator("gtt_mem", "cpu_mem", "vram_mem", mode="before")(na_to_none)


class ProcessUsage(BaseModel):
    # AMDSMI reports engine usage in nanoseconds
    gfx: ValueUnit | None
    enc: ValueUnit | None
    na_validator = field_validator("gfx", "enc", mode="before")(na_to_none)


class ProcessInfo(BaseModel):
    name: str
    pid: int

    mem: ValueUnit | None = None
    memory_usage: ProcessMemoryUsage
    usage: ProcessUsage
    cu_occupancy: ValueUnit | None = None
    na_validator = field_validator("mem", "cu_occupancy", mode="before")(na_to_none)


class ProcessListItem(BaseModel):
    process_info: ProcessInfo | str


class Processes(BaseModel):
    gpu: int
    process_list: List[ProcessListItem]


# FW
class FwListItem(BaseModel):
    fw_version: str
    fw_name: str


class Fw(BaseModel):
    gpu: int
    fw_list: List[FwListItem]


class AmdSmiListItem(BaseModel):
    gpu: int
    bdf: str
    uuid: str
    kfd_id: int
    node_id: int
    partition_id: int


class AmdSmiVersion(BaseModel):
    """Contains the versioning info for amd-smi"""

    tool: str | None = None
    version: str | None = None
    amdsmi_library_version: str | None = None
    rocm_version: str | None = None
    amdgpu_version: str | None = None
    amd_hsmp_driver_version: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def _stringify(cls, v):
        if v is None or isinstance(v, str):
            return v
        if isinstance(v, (bytes, bytearray)):
            return v.decode("utf-8", "ignore")
        if isinstance(v, (tuple, list)):
            return ".".join(str(x) for x in v)
        return str(v)


class PartitionAccelerator(BaseModel):
    """Contains the tition data for the GPUs"""

    gpu_id: int
    memory: str | None = None
    accelerator_type: str | None = None
    accelerator_profile_index: str | int | None = None
    partition_id: int | None = None


class PartitionMemory(BaseModel):
    """Memory Partition data"""

    gpu_id: int
    partition_type: str | None = None


class PartitionCompute(BaseModel):
    """Compute Partition data"""

    gpu_id: int
    partition_type: str | None = None


class Partition(BaseModel):
    """Contains the partition info for amd-smi"""

    memory_partition: list[PartitionMemory] = Field(default_factory=list)
    compute_partition: list[PartitionCompute] = Field(default_factory=list)


### STATIC DATA ###
class StaticAsic(BaseModel):
    market_name: str
    vendor_id: str
    vendor_name: str
    subvendor_id: str
    device_id: str
    subsystem_id: str
    rev_id: str
    asic_serial: str
    oam_id: int
    num_compute_units: int
    target_graphics_version: str


class StaticBus(AmdSmiBaseModel):
    bdf: str
    max_pcie_width: ValueUnit | None = None
    max_pcie_speed: ValueUnit | None = None
    pcie_interface_version: str = "unknown"
    slot_type: str = "unknown"


class StaticVbios(BaseModel):
    name: str
    build_date: str
    part_number: str
    version: str


class StaticLimit(AmdSmiBaseModel):
    max_power: ValueUnit | None
    min_power: ValueUnit | None
    socket_power: ValueUnit | None
    slowdown_edge_temperature: ValueUnit | None
    slowdown_hotspot_temperature: ValueUnit | None
    slowdown_vram_temperature: ValueUnit | None
    shutdown_edge_temperature: ValueUnit | None
    shutdown_hotspot_temperature: ValueUnit | None
    shutdown_vram_temperature: ValueUnit | None
    na_validator = field_validator(
        "max_power",
        "min_power",
        "socket_power",
        "slowdown_edge_temperature",
        "slowdown_hotspot_temperature",
        "slowdown_vram_temperature",
        "shutdown_edge_temperature",
        "shutdown_hotspot_temperature",
        "shutdown_vram_temperature",
        mode="before",
    )(na_to_none)


class StaticDriver(BaseModel):
    name: str
    version: str


class StaticBoard(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )

    amdsmi_model_number: str = Field(
        alias="model_number"
    )  # Model number is a reserved keyword for pydantic
    product_serial: str
    fru_id: str
    product_name: str
    manufacturer_name: str


class StaticPartition(BaseModel):

    compute_partition: str
    memory_partition: str
    partition_id: int


class StaticPolicy(BaseModel):
    policy_id: int
    policy_description: str


class StaticSocPstate(BaseModel):
    num_supported: int
    current_id: int
    policies: List[StaticPolicy]


class StaticXgmiPlpd(BaseModel):
    num_supported: int
    current_id: int
    plpds: List[StaticPolicy]


class StaticNuma(BaseModel):
    node: int
    affinity: int


class StaticVram(AmdSmiBaseModel):
    type: str
    vendor: str | None
    size: ValueUnit | None
    bit_width: ValueUnit | None
    max_bandwidth: ValueUnit | None = None
    na_validator = field_validator("vendor", "size", "bit_width", "max_bandwidth", mode="before")(
        na_to_none
    )


class StaticCacheInfoItem(AmdSmiBaseModel):
    cache: ValueUnit
    cache_properties: List[str]
    cache_size: ValueUnit | None
    cache_level: ValueUnit
    max_num_cu_shared: ValueUnit
    num_cache_instance: ValueUnit
    na_validator = field_validator("cache_size", mode="before")(na_to_none)


class StaticFrequencyLevels(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )

    Level_0: str = Field(..., alias="Level 0")
    Level_1: str | None = Field(default=None, alias="Level 1")
    Level_2: str | None = Field(default=None, alias="Level 2")


class StaticClockData(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    frequency: StaticFrequencyLevels

    current: int | None = Field(..., alias="current")
    na_validator = field_validator("current", mode="before")(na_to_none)


class AmdSmiStatic(BaseModel):
    gpu: int
    asic: StaticAsic
    bus: StaticBus
    vbios: StaticVbios | None
    limit: StaticLimit | None
    driver: StaticDriver | None
    board: StaticBoard
    soc_pstate: StaticSocPstate | None
    xgmi_plpd: StaticXgmiPlpd | None
    process_isolation: str
    numa: StaticNuma
    vram: StaticVram
    cache_info: List[StaticCacheInfoItem]
    partition: StaticPartition | None = None
    clock: StaticClockData | None = None
    na_validator_dict = field_validator("clock", mode="before")(na_to_none_dict)
    na_validator = field_validator("soc_pstate", "xgmi_plpd", "vbios", "limit", mode="before")(
        na_to_none
    )


# PAGES
class PageData(BaseModel):
    page_address: int | str
    page_size: int | str
    status: str
    value: int | None


class BadPages(BaseModel):
    gpu: int
    retired: list[PageData]


# Metric Data
class MetricUsage(BaseModel):
    gfx_activity: ValueUnit | None
    umc_activity: ValueUnit | None
    mm_activity: ValueUnit | None
    vcn_activity: list[ValueUnit | str | None]
    jpeg_activity: list[ValueUnit | str | None]
    gfx_busy_inst: dict[str, list[ValueUnit | str | None]] | None
    jpeg_busy: dict[str, list[ValueUnit | str | None]] | None
    vcn_busy: dict[str, list[ValueUnit | str | None]] | None
    na_validator_list = field_validator("vcn_activity", "jpeg_activity", mode="before")(
        na_to_none_list
    )
    na_validator = field_validator(
        "gfx_activity",
        "umc_activity",
        "mm_activity",
        "gfx_busy_inst",
        "jpeg_busy",
        "vcn_busy",
        mode="before",
    )(na_to_none)


class MetricPower(BaseModel):
    socket_power: ValueUnit | None
    gfx_voltage: ValueUnit | None
    soc_voltage: ValueUnit | None
    mem_voltage: ValueUnit | None
    throttle_status: str | None
    power_management: str | None
    na_validator = field_validator(
        "socket_power",
        "gfx_voltage",
        "soc_voltage",
        "mem_voltage",
        "throttle_status",
        "power_management",
        mode="before",
    )(na_to_none)


class MetricClockData(BaseModel):
    clk: ValueUnit | None
    min_clk: ValueUnit | None
    max_clk: ValueUnit | None
    clk_locked: int | str | dict | None
    deep_sleep: int | str | dict | None
    na_validator = field_validator(
        "clk", "min_clk", "max_clk", "clk_locked", "deep_sleep", mode="before"
    )(na_to_none)


class MetricTemperature(BaseModel):
    edge: ValueUnit | None
    hotspot: ValueUnit | None
    mem: ValueUnit | None
    na_validator = field_validator("edge", "hotspot", "mem", mode="before")(na_to_none)


class MetricPcie(BaseModel):
    width: int | None
    speed: ValueUnit | None
    bandwidth: ValueUnit | None
    replay_count: int | None
    l0_to_recovery_count: int | None
    replay_roll_over_count: int | None
    nak_sent_count: int | None
    nak_received_count: int | None
    current_bandwidth_sent: int | None
    current_bandwidth_received: int | None
    max_packet_size: int | None
    lc_perf_other_end_recovery: int | None
    na_validator = field_validator(
        "width",
        "speed",
        "bandwidth",
        "replay_count",
        "l0_to_recovery_count",
        "replay_roll_over_count",
        "nak_sent_count",
        "nak_received_count",
        "current_bandwidth_sent",
        "current_bandwidth_received",
        "max_packet_size",
        "lc_perf_other_end_recovery",
        mode="before",
    )(na_to_none)


class MetricEccTotals(BaseModel):
    total_correctable_count: int | None
    total_uncorrectable_count: int | None
    total_deferred_count: int | None
    cache_correctable_count: int | None
    cache_uncorrectable_count: int | None
    na_validator = field_validator(
        "total_correctable_count",
        "total_uncorrectable_count",
        "total_deferred_count",
        "cache_correctable_count",
        "cache_uncorrectable_count",
        mode="before",
    )(na_to_none)


class MetricErrorCounts(BaseModel):
    correctable_count: str | None
    uncorrectable_count: str | None
    deferred_count: str | None
    na_validator = field_validator(
        "correctable_count", "uncorrectable_count", "deferred_count", mode="before"
    )(na_to_none)


class MetricFan(BaseModel):
    speed: ValueUnit | None
    max: ValueUnit | None
    rpm: ValueUnit | None
    usage: ValueUnit | None
    na_validator = field_validator("speed", "max", "rpm", "usage", mode="before")(na_to_none)


class MetricVoltageCurve(BaseModel):
    point_0_frequency: ValueUnit | None
    point_0_voltage: ValueUnit | None
    point_1_frequency: ValueUnit | None
    point_1_voltage: ValueUnit | None
    point_2_frequency: ValueUnit | None
    point_2_voltage: ValueUnit | None

    na_validator = field_validator(
        "point_0_frequency",
        "point_0_voltage",
        "point_1_frequency",
        "point_1_voltage",
        "point_2_frequency",
        "point_2_voltage",
        mode="before",
    )(na_to_none)


class MetricEnergy(BaseModel):
    total_energy_consumption: ValueUnit | None
    na_validator = field_validator("total_energy_consumption", mode="before")(na_to_none)


class MetricMemUsage(BaseModel):
    total_vram: ValueUnit | None
    used_vram: ValueUnit | None
    free_vram: ValueUnit | None
    total_visible_vram: ValueUnit | None
    used_visible_vram: ValueUnit | None
    free_visible_vram: ValueUnit | None
    total_gtt: ValueUnit | None
    used_gtt: ValueUnit | None
    free_gtt: ValueUnit | None
    na_validator = field_validator(
        "total_vram",
        "used_vram",
        "free_vram",
        "total_visible_vram",
        "used_visible_vram",
        "free_visible_vram",
        "total_gtt",
        "used_gtt",
        "free_gtt",
        mode="before",
    )(na_to_none)


class MetricThrottleVu(BaseModel):
    xcp_0: list[ValueUnit | str | None] = None
    # Deprecated below
    value: dict[str, list[int | str]] | None = Field(deprecated=True, default=None)
    unit: str = Field(deprecated=True, default="")


class MetricThrottle(AmdSmiBaseModel):
    # At some point in time these changed from being int -> ValueUnit

    accumulation_counter: MetricThrottleVu | ValueUnit | None = None

    gfx_clk_below_host_limit_accumulated: MetricThrottleVu | ValueUnit | None = None
    gfx_clk_below_host_limit_power_accumulated: MetricThrottleVu | ValueUnit | None = None
    gfx_clk_below_host_limit_power_violation_activity: MetricThrottleVu | ValueUnit | None = None
    gfx_clk_below_host_limit_power_violation_status: MetricThrottleVu | ValueUnit | None = None
    gfx_clk_below_host_limit_violation_activity: MetricThrottleVu | ValueUnit | None = None
    gfx_clk_below_host_limit_violation_accumulated: MetricThrottleVu | ValueUnit | None = None
    gfx_clk_below_host_limit_violation_status: MetricThrottleVu | ValueUnit | None = None
    gfx_clk_below_host_limit_thermal_violation_accumulated: MetricThrottleVu | ValueUnit | None = (
        None
    )
    gfx_clk_below_host_limit_thermal_violation_activity: MetricThrottleVu | ValueUnit | None = None
    gfx_clk_below_host_limit_thermal_violation_status: MetricThrottleVu | ValueUnit | None = None
    gfx_clk_below_host_limit_thermal_accumulated: MetricThrottleVu | ValueUnit | None = None

    hbm_thermal_accumulated: MetricThrottleVu | ValueUnit | None = None
    hbm_thermal_violation_activity: MetricThrottleVu | ValueUnit | None = None
    hbm_thermal_violation_status: MetricThrottleVu | ValueUnit | None = None
    low_utilization_violation_accumulated: MetricThrottleVu | ValueUnit | None = None
    low_utilization_violation_activity: MetricThrottleVu | ValueUnit | None = None
    low_utilization_violation_status: MetricThrottleVu | ValueUnit | None = None
    ppt_accumulated: MetricThrottleVu | ValueUnit | None = None
    ppt_violation_activity: MetricThrottleVu | ValueUnit | None = None
    ppt_violation_status: MetricThrottleVu | ValueUnit | None = None
    prochot_accumulated: MetricThrottleVu | ValueUnit | None = None
    prochot_violation_activity: MetricThrottleVu | ValueUnit | None = None
    prochot_violation_status: MetricThrottleVu | ValueUnit | None = None
    socket_thermal_accumulated: MetricThrottleVu | ValueUnit | None = None
    socket_thermal_violation_activity: MetricThrottleVu | ValueUnit | None = None
    socket_thermal_violation_status: MetricThrottleVu | ValueUnit | None = None
    vr_thermal_accumulated: MetricThrottleVu | ValueUnit | None = None
    vr_thermal_violation_activity: MetricThrottleVu | ValueUnit | None = None
    vr_thermal_violation_status: MetricThrottleVu | ValueUnit | None = None

    total_gfx_clk_below_host_limit_accumulated: MetricThrottleVu | ValueUnit | None = None
    low_utilization_accumulated: MetricThrottleVu | ValueUnit | None = None
    total_gfx_clk_below_host_limit_violation_status: MetricThrottleVu | ValueUnit | None = None
    total_gfx_clk_below_host_limit_violation_activity: MetricThrottleVu | ValueUnit | None = None

    na_validator = field_validator(
        "accumulation_counter",
        "gfx_clk_below_host_limit_accumulated",
        "gfx_clk_below_host_limit_power_accumulated",
        "gfx_clk_below_host_limit_power_violation_activity",
        "gfx_clk_below_host_limit_power_violation_status",
        "gfx_clk_below_host_limit_violation_activity",
        "gfx_clk_below_host_limit_violation_accumulated",
        "gfx_clk_below_host_limit_violation_status",
        "gfx_clk_below_host_limit_thermal_violation_accumulated",
        "gfx_clk_below_host_limit_thermal_violation_activity",
        "gfx_clk_below_host_limit_thermal_violation_status",
        "gfx_clk_below_host_limit_thermal_accumulated",
        "hbm_thermal_accumulated",
        "hbm_thermal_violation_activity",
        "hbm_thermal_violation_status",
        "low_utilization_violation_accumulated",
        "low_utilization_violation_activity",
        "low_utilization_violation_status",
        "ppt_accumulated",
        "ppt_violation_activity",
        "ppt_violation_status",
        "prochot_accumulated",
        "prochot_violation_activity",
        "prochot_violation_status",
        "socket_thermal_accumulated",
        "socket_thermal_violation_activity",
        "socket_thermal_violation_status",
        "vr_thermal_accumulated",
        "vr_thermal_violation_activity",
        "vr_thermal_violation_status",
        "total_gfx_clk_below_host_limit_accumulated",
        "low_utilization_accumulated",
        "total_gfx_clk_below_host_limit_violation_status",
        "total_gfx_clk_below_host_limit_violation_activity",
        mode="before",
    )(na_to_none)


class EccData(BaseModel):
    "ECC counts collected per ecc block"

    correctable_count: int | None = 0
    uncorrectable_count: int | None = 0
    deferred_count: int | None = 0

    na_validator = field_validator(
        "correctable_count", "uncorrectable_count", "deferred_count", mode="before"
    )(na_to_none)


class AmdSmiMetric(BaseModel):
    gpu: int
    usage: MetricUsage
    power: MetricPower
    clock: dict[str, MetricClockData]
    temperature: MetricTemperature
    pcie: MetricPcie
    ecc: MetricEccTotals
    ecc_blocks: dict[str, EccData] | str
    fan: MetricFan
    voltage_curve: MetricVoltageCurve | None
    perf_level: str | dict | None
    xgmi_err: str | dict | None
    energy: MetricEnergy | None
    mem_usage: MetricMemUsage
    throttle: MetricThrottle

    na_validator = field_validator("xgmi_err", "perf_level", mode="before")(na_to_none)

    @field_validator("ecc_blocks", mode="before")
    @classmethod
    def validate_ecc_blocks(cls, value: dict[str, EccData] | str) -> dict[str, EccData]:
        """Validate the ecc_blocks field."""
        if isinstance(value, str):
            # If it's a string, we assume it's "N/A" and return an empty dict
            return {}
        return value

    @field_validator("energy", mode="before")
    @classmethod
    def validate_energy(cls, value: Any | None) -> MetricEnergy | None:
        """Validate the energy field."""
        if value == "N/A" or value is None:
            return None
        return value


class AmdSmiDataModel(DataModel):
    """Data model for amd-smi data.

    Optionals are used to allow for the data to be missing,
    This makes the data class more flexible for the analyzer
    which consumes only the required data. If any more data is
    required for the analyzer then they should not be set to
    default.
    """

    model_config = ConfigDict(
        str_min_length=1,
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    version: AmdSmiVersion | None = None
    gpu_list: list[AmdSmiListItem] | None = Field(default_factory=list)
    partition: Partition | None = None
    process: list[Processes] | None = Field(default_factory=list)
    firmware: list[Fw] | None = Field(default_factory=list)
    bad_pages: list[BadPages] | None = Field(default_factory=list)
    static: list[AmdSmiStatic] | None = Field(default_factory=list)
    metric: list[AmdSmiMetric] | None = Field(default_factory=list)

    def get_list(self, gpu: int) -> AmdSmiListItem | None:
        """Get the gpu list item for the given gpu id."""
        if self.gpu_list is None:
            return None
        for item in self.gpu_list:
            if item.gpu == gpu:
                return item
        return None

    def get_process(self, gpu: int) -> Processes | None:
        """Get the process data for the given gpu id."""
        if self.process is None:
            return None
        for item in self.process:
            if item.gpu == gpu:
                return item
        return None

    def get_firmware(self, gpu: int) -> Fw | None:
        """Get the firmware data for the given gpu id."""
        if self.firmware is None:
            return None
        for item in self.firmware:
            if item.gpu == gpu:
                return item
        return None

    def get_static(self, gpu: int) -> AmdSmiStatic | None:
        """Get the static data for the given gpu id."""
        if self.static is None:
            return None
        for item in self.static:
            if item.gpu == gpu:
                return item
        return None

    def get_bad_pages(self, gpu: int) -> BadPages | None:
        """Get the bad pages data for the given gpu id."""
        if self.bad_pages is None:
            return None
        for item in self.bad_pages:
            if item.gpu == gpu:
                return item
        return None
