from enum import Enum
from typing import Any, List, Optional

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    computed_field,
    field_validator,
)

from nodescraper.models.datamodel import DataModel, FileModel
from nodescraper.utils import find_annotation_in_container


def na_to_none(values: int | str):
    if values == "N/A":
        return None
    return values


def na_to_none_list(values: list[int | str]) -> List[int | str | None]:
    ret_list: List[int | str | None] = values.copy()
    for i in range(len(ret_list)):
        if ret_list[i] == "N/A":
            ret_list[i] = None
    return ret_list


def na_to_none_dict(values: dict[str, int | str]) -> dict[str, int | str | None]:
    ret_dict: dict[str, int | str | None] = values.copy()
    for key in ret_dict:
        if ret_dict[key] == "N/A":
            ret_dict[key] = None
    return ret_dict


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
    """A model for a value with a unit."""

    value: int | str | float
    # value: int | str | float
    unit: str = ""


# a = ValueUnit(23)


class EccState(Enum):
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    NONE = "NONE"
    PARITY = "PARITY"
    SING_C = "SING_C"
    MULT_UC = "MULT_UC"
    POISON = "POISON"
    NA = "N/A"


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
    max_pcie_width: ValueUnit
    max_pcie_speed: ValueUnit
    pcie_interface_version: str
    slot_type: str


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


class StaticRas(BaseModel):
    eeprom_version: str
    parity_schema: EccState
    single_bit_schema: EccState
    double_bit_schema: EccState
    poison_schema: EccState
    ecc_block_state: dict[str, EccState]


class StaticPartition(BaseModel):
    # The name for compute_partition has changed we will support both for now

    compute_partition: str = Field(
        validation_alias=AliasChoices("compute_partition", "accelerator_partition")
    )
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
    frequency_levels: StaticFrequencyLevels

    current_level: int | None = Field(..., alias="current level")
    na_validator = field_validator("current_level", mode="before")(na_to_none)


class AmdSmiStatic(BaseModel):
    gpu: int
    asic: StaticAsic
    bus: StaticBus
    vbios: StaticVbios | None
    limit: StaticLimit | None
    driver: StaticDriver
    board: StaticBoard
    ras: StaticRas
    soc_pstate: StaticSocPstate | None
    xgmi_plpd: StaticXgmiPlpd | None
    process_isolation: str
    numa: StaticNuma
    vram: StaticVram
    cache_info: List[StaticCacheInfoItem]
    partition: StaticPartition | None = None  # This has been removed in Amd-smi 26.0.0+d30a0afe+
    clock: dict[str, StaticClockData | None] | None = None
    na_validator_dict = field_validator("clock", mode="before")(na_to_none_dict)
    na_validator = field_validator("soc_pstate", "xgmi_plpd", "vbios", "limit", mode="before")(
        na_to_none
    )


### Metric Data ###


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
    value: dict[str, list[int | str]]
    unit: str = ""


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
    voltage_curve: MetricVoltageCurve
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


### LINK DATA ###


class LinkStatusTable(Enum):
    UP = "U"
    DOWN = "D"
    DISABLED = "X"


class BiDirectionalTable(Enum):
    SELF = "SELF"
    TRUE = "T"


class DmaTable(Enum):
    SELF = "SELF"
    TRUE = "T"


class AtomicsTable(Enum):
    SELF = "SELF"
    TRUE = "64,32"
    THIRTY_TWO = "32"
    SIXTY_FOUR = "64"


class LinkTypes(Enum):
    XGMI = "XGMI"
    PCIE = "PCIE"
    SELF = "SELF"


class AccessTable(Enum):
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"


# XGMI
class XgmiLink(BaseModel):
    gpu: int
    bdf: str
    read: ValueUnit | None
    write: ValueUnit | None
    na_validator = field_validator("read", "write", mode="before")(na_to_none)


class XgmiLinkMetrics(BaseModel):
    bit_rate: ValueUnit | None
    max_bandwidth: ValueUnit | None
    link_type: str
    links: List[XgmiLink]
    na_validator = field_validator("max_bandwidth", "bit_rate", mode="before")(na_to_none)


class XgmiMetrics(BaseModel):
    gpu: int
    bdf: str
    link_metrics: XgmiLinkMetrics


class XgmiLinks(BaseModel):
    gpu: int
    bdf: str
    link_status: list[LinkStatusTable]


class CoherentTable(Enum):
    COHERANT = "C"
    NON_COHERANT = "NC"
    SELF = "SELF"


# TOPO


class TopoLink(BaseModel):
    gpu: int
    bdf: str
    weight: int
    link_status: AccessTable
    link_type: LinkTypes
    num_hops: int
    bandwidth: str
    # The below fields are sometimes missing, so we use Optional
    coherent: CoherentTable | None = None
    atomics: AtomicsTable | None = None
    dma: DmaTable | None = None
    bi_dir: BiDirectionalTable | None = None

    @computed_field
    @property
    def bandwidth_from(self) -> int | None:
        """Get the bandwidth from the link."""
        bw_split = self.bandwidth.split("-")
        if len(bw_split) == 2:
            return int(bw_split[0])
        else:
            # If the bandwidth is not in the expected format, return None
            return None

    @computed_field
    @property
    def bandwidth_to(self) -> int | None:
        """Get the bandwidth to the link."""
        bw_split = self.bandwidth.split("-")
        if len(bw_split) == 2:
            return int(bw_split[1])
        else:
            # If the bandwidth is not in the expected format, return None
            return None


class Topo(BaseModel):
    gpu: int
    bdf: str
    links: List[TopoLink]


# PROCESS DATA
class ProcessMemoryUsage(BaseModel):
    gtt_mem: ValueUnit | None
    cpu_mem: ValueUnit | None
    vram_mem: ValueUnit | None
    na_validator = field_validator("gtt_mem", "cpu_mem", "vram_mem", mode="before")(na_to_none)


class ProcessUsage(BaseModel):
    gfx: ValueUnit | None
    enc: ValueUnit | None
    na_validator = field_validator("gfx", "enc", mode="before")(na_to_none)


class ProcessInfo(BaseModel):
    name: str
    pid: int
    memory_usage: ProcessMemoryUsage
    mem_usage: ValueUnit | None
    usage: ProcessUsage
    na_validator = field_validator("mem_usage", mode="before")(na_to_none)


class ProcessListItem(BaseModel):
    process_info: ProcessInfo | str


class Processes(BaseModel):
    gpu: int
    process_list: List[ProcessListItem]


# FW
class FwListItem(BaseModel):
    fw_id: str
    fw_version: str


class Fw(BaseModel):
    gpu: int
    fw_list: List[FwListItem]


# AMD SMI LIST
class AmdSmiListItem(BaseModel):
    gpu: int
    bdf: str
    uuid: str
    kfd_id: int
    node_id: int
    partition_id: int


# PAGES
class PageData(BaseModel):
    page_address: int | str
    page_size: int | str
    status: str


class BadPages(BaseModel):
    gpu: int
    retired: str | PageData | list[PageData]
    pending: str | PageData | list[PageData]
    un_res: str | PageData | list[PageData]


class AmdSmiMetricPcieData(BaseModel):
    "Data in pcie subfield of metrics command"

    width: NonNegativeInt
    speed: NonNegativeFloat
    bandwidth: Optional[NonNegativeFloat] = 0
    replay_count: Optional[int] = 0
    l0_to_recovery_count: Optional[int] = 0
    replay_roll_over_count: Optional[int] = 0
    nak_sent_count: Optional[int] = 0
    nak_received_count: Optional[int] = 0


class AmdSmiMetricEccData(BaseModel):
    "ECC info collected per ecc block"

    umc: EccData = EccData()
    sdma: EccData = EccData()
    gfx: EccData = EccData()
    mmhub: EccData = EccData()
    pcie_bif: EccData = EccData()
    hdp: EccData = EccData()
    xgmi_wafl: EccData = EccData()


class AmdSmiTstData(BaseModel):
    "Summary of amdsmitst results, with list and count of passing/skipped/failed tests"

    passed_tests: list[str] = Field(default_factory=list)
    skipped_tests: list[str] = Field(default_factory=list)
    failed_tests: list[str] = Field(default_factory=list)
    passed_test_count: int = 0
    skipped_test_count: int = 0
    failed_test_count: int = 0


class AmdSmiVersion(BaseModel):
    """Contains the versioning info for amd-smi"""

    tool: str | None = None
    version: str | None = None
    amdsmi_library_version: str | None = None
    rocm_version: str | None = None
    amdgpu_version: str | None = None
    amd_hsmp_driver_version: str | None = None


class PartitionCurrent(BaseModel):
    """Contains the Current Partition data for the GPUs"""

    gpu_id: int
    memory: str | None = None
    accelerator_type: str | None = None
    accelerator_profile_index: str | int | None = None
    partition_id: str | int | None = None  # Right now this is a string but it looks like an int


class PartitionMemory(BaseModel):
    """Memory Partition data"""

    gpu_id: int
    memory_partition_caps: str | None = None
    current_partition_id: str | None = None


class PartitionProfiles(AmdSmiBaseModel):
    """Partition Profiles data"""

    gpu_id: int
    profile_index: str | None = None
    memory_partition_caps: str | None = None
    accelerator_type: str | None = None
    partition_id: str | None = None
    num_partitions: str | None = None
    num_resources: str | None = None
    resource_index: str | None = None
    resource_type: str | None = None
    resource_instances: str | None = None
    resources_shared: str | None = None


class PartitionResources(AmdSmiBaseModel):
    """Partition Resources"""

    # This does not have gpu_id field for some reason.
    # gpu_id: int
    resource_index: str | None = None
    resource_type: str | None = None
    resource_instances: str | None = None
    resources_shared: str | None = None


# Partition info
class Partition(BaseModel):
    """Contains the partition info for amd-smi"""

    current_partition: list[PartitionCurrent] = Field(default_factory=list)
    memory_partition: list[PartitionMemory] = Field(default_factory=list)
    # Right now partition_profiles and partition_resources is all N/A by amd-smi so placeholder dict until better defined
    partition_profiles: list[dict] = Field(default_factory=list)
    partition_resources: list[dict] = Field(default_factory=list)


class AmdSmiData(DataModel):
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
    topology: list[Topo] | None = Field(default_factory=list)
    static: list[AmdSmiStatic] | None = Field(default_factory=list)
    metric: list[AmdSmiMetric] | None = Field(default_factory=list)
    firmware: list[Fw] | None = Field(default_factory=list)
    bad_pages: list[BadPages] | None = Field(default_factory=list)
    xgmi_metric: list[XgmiMetrics] | None = Field(default_factory=list)
    xgmi_link: list[XgmiLinks] | None = Field(default_factory=list)
    cper_data: list[FileModel] | None = Field(default_factory=list)
    amdsmitst_data: AmdSmiTstData

    def get_list(self, gpu: int) -> AmdSmiListItem | None:
        """Get the gpu list item for the given gpu id."""
        if self.gpu_list is None:
            return None
        for item in self.gpu_list:
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

    def get_metric(self, gpu: int) -> AmdSmiMetric | None:
        """Get the metric data for the given gpu id."""
        if self.metric is None:
            return None
        for item in self.metric:
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

    def get_topology(self, gpu: int) -> Topo | None:
        """Get the topology data for the given gpu id."""
        if self.topology is None:
            return None
        for item in self.topology:
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

    def get_bad_pages(self, gpu: int) -> BadPages | None:
        """Get the bad pages data for the given gpu id."""
        if self.bad_pages is None:
            return None
        for item in self.bad_pages:
            if item.gpu == gpu:
                return item
        return None

    @property
    def amdsmimetricpcie_data(self) -> dict[int, AmdSmiMetricPcieData]:
        """Get the pcie data for the given gpu id."""
        return {
            item.gpu: AmdSmiMetricPcieData(
                width=item.pcie.width if item.pcie.width else 0,
                speed=float(item.pcie.speed.value) if item.pcie.speed else 0,
                bandwidth=float(item.pcie.bandwidth.value) if item.pcie.bandwidth else 0,
                replay_count=item.pcie.replay_count,
                l0_to_recovery_count=item.pcie.l0_to_recovery_count,
                replay_roll_over_count=item.pcie.replay_roll_over_count,
                nak_sent_count=item.pcie.nak_sent_count,
                nak_received_count=item.pcie.nak_received_count,
            )
            for item in self.metric or []
        }

    @property
    def amdsmimetricecc_data(self) -> dict[int, AmdSmiMetricEccData]:
        """Get the ecc data for the given gpu id."""
        amdsmimetric_ret = {}
        for item in self.metric or []:
            if isinstance(item.ecc_blocks, str):
                # If ecc_blocks is a string, it means no ECC data is available
                continue
            amdsmimetric_ret[item.gpu] = AmdSmiMetricEccData(
                umc=item.ecc_blocks.get("UMC", EccData()),
                sdma=item.ecc_blocks.get("SDMA", EccData()),
                gfx=item.ecc_blocks.get("GFX", EccData()),
                mmhub=item.ecc_blocks.get("MMHUB", EccData()),
                pcie_bif=item.ecc_blocks.get("PCIE_BIF", EccData()),
                hdp=item.ecc_blocks.get("HDP", EccData()),
                xgmi_wafl=item.ecc_blocks.get("XGMI_WAFL", EccData()),
            )
        return amdsmimetric_ret
