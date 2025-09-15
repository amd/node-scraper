from enum import Enum
from typing import List

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from nodescraper.models.datamodel import DataModel
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
    unit: str = ""


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
