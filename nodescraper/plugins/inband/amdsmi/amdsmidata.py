import re
from typing import Any, List, Mapping, Optional, Union

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


def na_to_none(values: Union[int, str]):
    if values == "N/A":
        return None
    return values


def na_to_none_list(values: List[Union[int, str, None]]) -> List[Union[int, str, None]]:
    ret_list: List[Union[int, str, None]] = values.copy()
    for i in range(len(ret_list)):
        if ret_list[i] == "N/A":
            ret_list[i] = None
    return ret_list


def na_to_none_dict(values: object) -> Optional[dict[str, Any]]:
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

    def __init__(self, **data):
        # Convert  Union[int, str, float] -> ValueUnit
        for field_name, field_type in self.__class__.model_fields.items():
            annotation = field_type.annotation
            target_type, container = find_annotation_in_container(annotation, ValueUnit)
            if target_type is None:
                continue

            if field_name in data and isinstance(data[field_name], (int, str, float)):
                # If the field is a primitive type, convert it to ValueUnit dict for validator
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

    value: Union[int, float, str]
    unit: str = ""

    @model_validator(mode="before")
    @classmethod
    def _coerce(cls, v):
        # treat N/A as None
        def na(x) -> bool:
            return x is None or (isinstance(x, str) and x.strip().upper() in {"N/A", "NA", ""})

        if na(v):
            return None

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
    gtt_mem: Optional[ValueUnit]
    cpu_mem: Optional[ValueUnit]
    vram_mem: Optional[ValueUnit]

    na_validator = field_validator("gtt_mem", "cpu_mem", "vram_mem", mode="before")(na_to_none)


class ProcessUsage(BaseModel):
    # AMDSMI reports engine usage in nanoseconds
    gfx: Optional[ValueUnit]
    enc: Optional[ValueUnit]
    na_validator = field_validator("gfx", "enc", mode="before")(na_to_none)


class ProcessInfo(BaseModel):
    name: str
    pid: int

    mem: Optional[ValueUnit] = None
    memory_usage: ProcessMemoryUsage
    usage: ProcessUsage
    cu_occupancy: Optional[ValueUnit] = None
    na_validator = field_validator("mem", "cu_occupancy", mode="before")(na_to_none)


class ProcessListItem(BaseModel):
    process_info: Union[ProcessInfo, str]


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

    tool: Optional[str] = None
    version: Optional[str] = None
    amdsmi_library_version: Optional[str] = None
    rocm_version: Optional[str] = None
    amdgpu_version: Optional[str] = None
    amd_hsmp_driver_version: Optional[str] = None

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
    """Accelerator partition data"""

    gpu_id: int
    memory: Optional[str] = None
    accelerator_type: Optional[str] = None
    accelerator_profile_index: Optional[Union[str, int]] = None
    partition_id: Optional[int] = None


class PartitionMemory(BaseModel):
    """Memory Partition data"""

    gpu_id: int
    partition_type: Optional[str] = None


class PartitionCompute(BaseModel):
    """Compute Partition data"""

    gpu_id: int
    partition_type: Optional[str] = None


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
    max_pcie_width: Optional[ValueUnit] = None
    max_pcie_speed: Optional[ValueUnit] = None
    pcie_interface_version: str = "unknown"
    slot_type: str = "unknown"


class StaticVbios(BaseModel):
    name: str
    build_date: str
    part_number: str
    version: str


class StaticLimit(AmdSmiBaseModel):
    max_power: Optional[ValueUnit] = None
    min_power: Optional[ValueUnit] = None
    socket_power: Optional[ValueUnit] = None
    slowdown_edge_temperature: Optional[ValueUnit] = None
    slowdown_hotspot_temperature: Optional[ValueUnit] = None
    slowdown_vram_temperature: Optional[ValueUnit] = None
    shutdown_edge_temperature: Optional[ValueUnit] = None
    shutdown_hotspot_temperature: Optional[ValueUnit] = None
    shutdown_vram_temperature: Optional[ValueUnit] = None
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
    vendor: Optional[str]
    size: Optional[ValueUnit]
    bit_width: Optional[ValueUnit]
    max_bandwidth: Optional[ValueUnit] = None
    na_validator = field_validator("vendor", "size", "bit_width", "max_bandwidth", mode="before")(
        na_to_none
    )


class StaticCacheInfoItem(AmdSmiBaseModel):
    cache: ValueUnit
    cache_properties: List[str]
    cache_size: Optional[ValueUnit]
    cache_level: ValueUnit
    max_num_cu_shared: ValueUnit
    num_cache_instance: ValueUnit
    na_validator = field_validator("cache_size", mode="before")(na_to_none)


class StaticFrequencyLevels(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )

    Level_0: str = Field(..., alias="Level 0")
    Level_1: Optional[str] = Field(default=None, alias="Level 1")
    Level_2: Optional[str] = Field(default=None, alias="Level 2")


class StaticClockData(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
    )
    frequency: StaticFrequencyLevels

    current: Optional[int] = Field(..., alias="current")
    na_validator = field_validator("current", mode="before")(na_to_none)


class AmdSmiStatic(BaseModel):
    """Contains all static data"""

    gpu: int
    asic: StaticAsic
    bus: StaticBus
    vbios: Optional[StaticVbios]
    limit: Optional[StaticLimit]
    driver: Optional[StaticDriver]
    board: StaticBoard
    soc_pstate: Optional[StaticSocPstate]
    xgmi_plpd: Optional[StaticXgmiPlpd]
    process_isolation: str
    numa: StaticNuma
    vram: StaticVram
    cache_info: List[StaticCacheInfoItem]
    partition: Optional[StaticPartition] = None
    clock: Optional[StaticClockData] = None
    na_validator_dict = field_validator("clock", mode="before")(na_to_none_dict)
    na_validator = field_validator("soc_pstate", "xgmi_plpd", "vbios", "limit", mode="before")(
        na_to_none
    )


# PAGES
class PageData(BaseModel):
    page_address: Union[int, str]
    page_size: Union[int, str]
    status: str
    value: Optional[int]


class BadPages(BaseModel):
    gpu: int
    retired: list[PageData]


# Metric Data
class MetricUsage(BaseModel):
    gfx_activity: Optional[ValueUnit]
    umc_activity: Optional[ValueUnit]
    mm_activity: Optional[ValueUnit]
    vcn_activity: list[Optional[Union[ValueUnit, str]]]
    jpeg_activity: list[Optional[Union[ValueUnit, str]]]
    gfx_busy_inst: Optional[dict[str, list[Optional[Union[ValueUnit, str]]]]]
    jpeg_busy: Optional[dict[str, list[Optional[Union[ValueUnit, str]]]]]
    vcn_busy: Optional[dict[str, list[Optional[Union[ValueUnit, str]]]]]
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
    socket_power: Optional[ValueUnit]
    gfx_voltage: Optional[ValueUnit]
    soc_voltage: Optional[ValueUnit]
    mem_voltage: Optional[ValueUnit]
    throttle_status: Optional[str]
    power_management: Optional[str]
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
    clk: Optional[ValueUnit]
    min_clk: Optional[ValueUnit]
    max_clk: Optional[ValueUnit]
    clk_locked: Optional[Union[int, str, dict]]
    deep_sleep: Optional[Union[int, str, dict]]
    na_validator = field_validator(
        "clk", "min_clk", "max_clk", "clk_locked", "deep_sleep", mode="before"
    )(na_to_none)


class MetricTemperature(BaseModel):
    edge: Optional[ValueUnit]
    hotspot: Optional[ValueUnit]
    mem: Optional[ValueUnit]
    na_validator = field_validator("edge", "hotspot", "mem", mode="before")(na_to_none)


class MetricPcie(BaseModel):
    width: Optional[int]
    speed: Optional[ValueUnit]
    bandwidth: Optional[ValueUnit]
    replay_count: Optional[int]
    l0_to_recovery_count: Optional[int]
    replay_roll_over_count: Optional[int]
    nak_sent_count: Optional[int]
    nak_received_count: Optional[int]
    current_bandwidth_sent: Optional[int]
    current_bandwidth_received: Optional[int]
    max_packet_size: Optional[int]
    lc_perf_other_end_recovery: Optional[int]
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
    total_correctable_count: Optional[int]
    total_uncorrectable_count: Optional[int]
    total_deferred_count: Optional[int]
    cache_correctable_count: Optional[int]
    cache_uncorrectable_count: Optional[int]
    na_validator = field_validator(
        "total_correctable_count",
        "total_uncorrectable_count",
        "total_deferred_count",
        "cache_correctable_count",
        "cache_uncorrectable_count",
        mode="before",
    )(na_to_none)


class MetricErrorCounts(BaseModel):
    correctable_count: Optional[str]
    uncorrectable_count: Optional[str]
    deferred_count: Optional[str]
    na_validator = field_validator(
        "correctable_count", "uncorrectable_count", "deferred_count", mode="before"
    )(na_to_none)


class MetricFan(BaseModel):
    speed: Optional[ValueUnit]
    max: Optional[ValueUnit]
    rpm: Optional[ValueUnit]
    usage: Optional[ValueUnit]
    na_validator = field_validator("speed", "max", "rpm", "usage", mode="before")(na_to_none)


class MetricVoltageCurve(BaseModel):
    point_0_frequency: Optional[ValueUnit]
    point_0_voltage: Optional[ValueUnit]
    point_1_frequency: Optional[ValueUnit]
    point_1_voltage: Optional[ValueUnit]
    point_2_frequency: Optional[ValueUnit]
    point_2_voltage: Optional[ValueUnit]

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
    total_energy_consumption: Optional[ValueUnit]
    na_validator = field_validator("total_energy_consumption", mode="before")(na_to_none)


class MetricMemUsage(BaseModel):
    total_vram: Optional[ValueUnit]
    used_vram: Optional[ValueUnit]
    free_vram: Optional[ValueUnit]
    total_visible_vram: Optional[ValueUnit]
    used_visible_vram: Optional[ValueUnit]
    free_visible_vram: Optional[ValueUnit]
    total_gtt: Optional[ValueUnit]
    used_gtt: Optional[ValueUnit]
    free_gtt: Optional[ValueUnit]
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
    xcp_0: Optional[list[Optional[Union[ValueUnit, str]]]] = None
    # Deprecated below
    value: Optional[dict[str, list[Union[int, str]]]] = Field(deprecated=True, default=None)
    unit: str = Field(deprecated=True, default="")


class MetricThrottle(AmdSmiBaseModel):
    # At some point in time these changed from being int -> ValueUnit

    accumulation_counter: Optional[Union[MetricThrottleVu, ValueUnit]] = None

    gfx_clk_below_host_limit_accumulated: Optional[Union[MetricThrottleVu, ValueUnit]] = None
    gfx_clk_below_host_limit_power_accumulated: Optional[Union[MetricThrottleVu, ValueUnit]] = None
    gfx_clk_below_host_limit_power_violation_activity: Optional[
        Union[MetricThrottleVu, ValueUnit]
    ] = None
    gfx_clk_below_host_limit_power_violation_status: Optional[
        Union[MetricThrottleVu, ValueUnit]
    ] = None
    gfx_clk_below_host_limit_violation_activity: Optional[Union[MetricThrottleVu, ValueUnit]] = None
    gfx_clk_below_host_limit_violation_accumulated: Optional[Union[MetricThrottleVu, ValueUnit]] = (
        None
    )
    gfx_clk_below_host_limit_violation_status: Optional[Union[MetricThrottleVu, ValueUnit]] = None
    gfx_clk_below_host_limit_thermal_violation_accumulated: Optional[
        Union[MetricThrottleVu, ValueUnit]
    ] = None
    gfx_clk_below_host_limit_thermal_violation_activity: Optional[
        Union[MetricThrottleVu, ValueUnit]
    ] = None
    gfx_clk_below_host_limit_thermal_violation_status: Optional[
        Union[MetricThrottleVu, ValueUnit]
    ] = None
    gfx_clk_below_host_limit_thermal_accumulated: Optional[Union[MetricThrottleVu, ValueUnit]] = (
        None
    )

    hbm_thermal_accumulated: Optional[Union[MetricThrottleVu, ValueUnit]] = None
    hbm_thermal_violation_activity: Optional[Union[MetricThrottleVu, ValueUnit]] = None
    hbm_thermal_violation_status: Optional[Union[MetricThrottleVu, ValueUnit]] = None
    low_utilization_violation_accumulated: Optional[Union[MetricThrottleVu, ValueUnit]] = None
    low_utilization_violation_activity: Optional[Union[MetricThrottleVu, ValueUnit]] = None
    low_utilization_violation_status: Optional[Union[MetricThrottleVu, ValueUnit]] = None
    ppt_accumulated: Optional[Union[MetricThrottleVu, ValueUnit]] = None
    ppt_violation_activity: Optional[Union[MetricThrottleVu, ValueUnit]] = None
    ppt_violation_status: Optional[Union[MetricThrottleVu, ValueUnit]] = None
    prochot_accumulated: Optional[Union[MetricThrottleVu, ValueUnit]] = None
    prochot_violation_activity: Optional[Union[MetricThrottleVu, ValueUnit]] = None
    prochot_violation_status: Optional[Union[MetricThrottleVu, ValueUnit]] = None
    socket_thermal_accumulated: Optional[Union[MetricThrottleVu, ValueUnit]] = None
    socket_thermal_violation_activity: Optional[Union[MetricThrottleVu, ValueUnit]] = None
    socket_thermal_violation_status: Optional[Union[MetricThrottleVu, ValueUnit]] = None
    vr_thermal_accumulated: Optional[Union[MetricThrottleVu, ValueUnit]] = None
    vr_thermal_violation_activity: Optional[Union[MetricThrottleVu, ValueUnit]] = None
    vr_thermal_violation_status: Optional[Union[MetricThrottleVu, ValueUnit]] = None

    total_gfx_clk_below_host_limit_accumulated: Optional[Union[MetricThrottleVu, ValueUnit]] = None
    low_utilization_accumulated: Optional[Union[MetricThrottleVu, ValueUnit]] = None
    total_gfx_clk_below_host_limit_violation_status: Optional[
        Union[MetricThrottleVu, ValueUnit]
    ] = None
    total_gfx_clk_below_host_limit_violation_activity: Optional[
        Union[MetricThrottleVu, ValueUnit]
    ] = None

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

    correctable_count: Optional[int] = 0
    uncorrectable_count: Optional[int] = 0
    deferred_count: Optional[int] = 0

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
    ecc_blocks: Union[dict[str, EccData], str]
    fan: MetricFan
    voltage_curve: Optional[MetricVoltageCurve]
    perf_level: Optional[Union[str, dict]]
    xgmi_err: Optional[Union[str, dict]]
    energy: Optional[MetricEnergy]
    mem_usage: MetricMemUsage
    throttle: MetricThrottle

    na_validator = field_validator("xgmi_err", "perf_level", mode="before")(na_to_none)

    @field_validator("ecc_blocks", mode="before")
    @classmethod
    def validate_ecc_blocks(cls, value: Union[dict[str, EccData], str]) -> dict[str, EccData]:
        """Validate the ecc_blocks field."""
        if isinstance(value, str):
            # If it's a string, we assume it's "N/A" and return an empty dict
            return {}
        return value

    @field_validator("energy", mode="before")
    @classmethod
    def validate_energy(cls, value: Optional[Any]) -> Optional[MetricEnergy]:
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

    version: Optional[AmdSmiVersion] = None
    gpu_list: Optional[list[AmdSmiListItem]] = Field(default_factory=list)
    partition: Optional[Partition] = None
    process: Optional[list[Processes]] = Field(default_factory=list)
    firmware: Optional[list[Fw]] = Field(default_factory=list)
    bad_pages: Optional[list[BadPages]] = Field(default_factory=list)
    static: Optional[list[AmdSmiStatic]] = Field(default_factory=list)
    metric: Optional[list[AmdSmiMetric]] = Field(default_factory=list)

    def get_list(self, gpu: int) -> Optional[AmdSmiListItem]:
        """Get the gpu list item for the given gpu id."""
        if self.gpu_list is None:
            return None
        for item in self.gpu_list:
            if item.gpu == gpu:
                return item
        return None

    def get_process(self, gpu: int) -> Optional[Processes]:
        """Get the process data for the given gpu id."""
        if self.process is None:
            return None
        for item in self.process:
            if item.gpu == gpu:
                return item
        return None

    def get_firmware(self, gpu: int) -> Optional[Fw]:
        """Get the firmware data for the given gpu id."""
        if self.firmware is None:
            return None
        for item in self.firmware:
            if item.gpu == gpu:
                return item
        return None

    def get_static(self, gpu: int) -> Optional[AmdSmiStatic]:
        """Get the static data for the given gpu id."""
        if self.static is None:
            return None
        for item in self.static:
            if item.gpu == gpu:
                return item
        return None

    def get_bad_pages(self, gpu: int) -> Optional[BadPages]:
        """Get the bad pages data for the given gpu id."""
        if self.bad_pages is None:
            return None
        for item in self.bad_pages:
            if item.gpu == gpu:
                return item
        return None
