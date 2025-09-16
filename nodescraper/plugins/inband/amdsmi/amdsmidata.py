import re
from enum import Enum
from typing import Any, List, Mapping

from pydantic import (
    AliasChoices,
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


def na_to_none_list(values: list[int | str]) -> List[int | str | None]:
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
    if not isinstance(values, Mapping):  # guard: pydantic may pass non-dicts in 'before' mode
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


class EccState(Enum):
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    NONE = "NONE"
    PARITY = "PARITY"
    SING_C = "SING_C"
    MULT_UC = "MULT_UC"
    POISON = "POISON"
    NA = "N/A"


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


class CoherentTable(Enum):
    COHERANT = "C"
    NON_COHERANT = "NC"
    SELF = "SELF"


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


class PartitionCurrent(BaseModel):
    """Contains the Current Partition data for the GPUs"""

    gpu_id: int
    memory: str | None = None
    accelerator_type: str | None = None
    accelerator_profile_index: str | int | None = None
    partition_id: int | None = None


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


class Partition(BaseModel):
    """Contains the partition info for amd-smi"""

    current_partition: list[PartitionCurrent] = Field(default_factory=list)
    memory_partition: list[PartitionMemory] = Field(default_factory=list)
    partition_profiles: list[dict] = Field(default_factory=list)
    partition_resources: list[dict] = Field(default_factory=list)


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
    # driver: StaticDriver
    board: StaticBoard
    # ras: StaticRas
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
    static: list[AmdSmiStatic] | None = Field(default_factory=list)

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
