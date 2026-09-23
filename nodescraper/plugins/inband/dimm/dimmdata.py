###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
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
from typing import ClassVar, Optional

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    computed_field,
    field_validator,
)
from typing_extensions import override

from nodescraper.models import DataModel

# Byte multiplier for every size unit that dmidecode may report for a module.
SIZE_UNITS = {
    "B": 1,
    "KB": 1024,
    "MB": 1024**2,
    "GB": 1024**3,
    "TB": 1024**4,
    "PB": 1024**5,
}

# Units considered when rendering a byte count, largest first so that the
# shortest exact representation wins.
DISPLAY_UNITS = ("PB", "TB", "GB", "MB", "KB")

# Field values that mean "nothing here" rather than a real value.
PLACEHOLDERS = frozenset(
    {
        "",
        "unknown",
        "not specified",
        "not provided",
        "none",
        "no module installed",
        "[empty]",
        "to be filled by o.e.m.",
    }
)

# SMBIOS memory type codes (SMBIOS spec 7.18.2). dmidecode resolves these
# itself; on Windows they arrive as raw codes in SMBIOSMemoryType.
SMBIOS_MEMORY_TYPES = {
    1: "Other",
    2: "Unknown",
    3: "DRAM",
    15: "SDRAM",
    16: "SGRAM",
    17: "RDRAM",
    18: "DDR",
    19: "DDR2",
    20: "DDR2 FB-DIMM",
    24: "DDR3",
    25: "FBD2",
    26: "DDR4",
    27: "LPDDR",
    28: "LPDDR2",
    29: "LPDDR3",
    30: "LPDDR4",
    31: "Logical non-volatile device",
    32: "HBM",
    33: "HBM2",
    34: "DDR5",
    35: "LPDDR5",
    36: "HBM3",
}

# Win32_PhysicalMemory FormFactor codes. WMI uses its own enumeration here,
# which does not match the SMBIOS form factor codes.
WMI_FORM_FACTORS = {
    0: "Unknown",
    1: "Other",
    2: "SIP",
    3: "DIP",
    4: "ZIP",
    5: "SOJ",
    6: "Proprietary",
    7: "SIMM",
    8: "DIMM",
    9: "TSOP",
    10: "PGA",
    11: "RIMM",
    12: "SODIMM",
    13: "SRIMM",
    14: "SMD",
    15: "SSMP",
    16: "QFP",
    17: "TQFP",
    18: "SOIC",
    19: "LCC",
    20: "PLCC",
    21: "BGA",
    22: "FPBGA",
    23: "LGA",
}


def format_size(size_bytes: int) -> str:
    """Render a byte count using the largest unit that divides it evenly.

    Args:
        size_bytes (int): size in bytes.

    Returns:
        str: human readable size, e.g. "64GB".
    """
    for unit in DISPLAY_UNITS:
        factor = SIZE_UNITS[unit]
        if size_bytes >= factor and not size_bytes % factor:
            return f"{size_bytes // factor}{unit}"
    return f"{size_bytes}B"


def clean(value: str) -> Optional[str]:
    """Normalise a text field, mapping placeholder values to None."""
    value = value.strip()
    return value if value.lower() not in PLACEHOLDERS else None


def parse_value(value: str) -> Optional[tuple[int, str]]:
    """Split a numeric field into its number and its unit.

    Every numeric field either source reports is a count followed by an
    optional unit, e.g. "64 GB", "4800 MT/s", "80 bits" or a bare "2".

    Args:
        value (str): raw field.

    Returns:
        Optional[tuple[int, str]]: the number and its unit, the unit being
        empty when the field carries none. None when the field does not start
        with a number at all, e.g. "No Module Installed" or "DDR5".
    """
    number, _, unit = value.strip().partition(" ")
    if not number.isdigit():
        return None

    return int(number), unit.strip()


def parse_size(value: str) -> Optional[int]:
    """Convert a size field such as "64 GB" into bytes.

    Args:
        value (str): raw size field.

    Returns:
        Optional[int]: size in bytes, or None when the slot holds no usable
        module, e.g. "No Module Installed", "Unknown" or a zero size.
    """
    parsed = parse_value(value)
    if not parsed:
        return None

    size, unit = parsed
    # A size with no unit is already a byte count, which is how
    # Win32_PhysicalMemory reports capacity.
    factor = SIZE_UNITS.get(unit.upper() or "B")
    if not factor:
        return None

    return size * factor or None


def decode(codes: dict[int, str], value: str) -> Optional[str]:
    """Resolve an SMBIOS or WMI enum code to its name.

    Values that are already named, as dmidecode reports them, pass through
    untouched.

    Args:
        codes (dict[int, str]): enum table to resolve against.
        value (str): raw code or name.

    Returns:
        Optional[str]: the decoded name, the raw code if the table does not
        cover it, or None if the value carries no meaning.
    """
    parsed = parse_value(value)
    # dmidecode names the value outright, Windows reports a bare enum code.
    if not parsed or parsed[1]:
        return clean(value)

    code = parsed[0]
    return clean(codes.get(code, f"Type {code}"))


class DimmInfo(BaseModel):
    """Details of a single populated memory slot.

    Every field is aliased to the names dmidecode and Win32_PhysicalMemory use
    for it, so a raw record from either source validates straight into the
    model and the units, enum codes and placeholder values are decoded here
    rather than by the caller.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(populate_by_name=True)

    size_bytes: int = Field(
        validation_alias=AliasChoices("size_bytes", "Size", "Capacity"),
        description="Module capacity in bytes",
    )
    locator: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("locator", "Locator", "DeviceLocator"),
        description="Slot the module is installed in",
    )
    bank_locator: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("bank_locator", "Bank Locator", "BankLabel"),
        description="Memory bank the slot belongs to",
    )
    manufacturer: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("manufacturer", "Manufacturer"),
    )
    part_number: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("part_number", "Part Number", "PartNumber"),
    )
    serial_number: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("serial_number", "Serial Number", "SerialNumber"),
    )
    memory_type: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("memory_type", "Type", "SMBIOSMemoryType"),
        description="Memory technology, e.g. DDR5",
    )
    form_factor: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("form_factor", "Form Factor", "FormFactor"),
        description="Physical form factor, e.g. DIMM",
    )
    speed_mts: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("speed_mts", "Speed"),
        description="Rated speed in MT/s",
    )
    configured_speed_mts: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices(
            "configured_speed_mts", "Configured Memory Speed", "ConfiguredClockSpeed"
        ),
        description="Speed the module is running at in MT/s",
    )
    rank: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("rank", "Rank"),
    )
    data_width_bits: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("data_width_bits", "Data Width", "DataWidth"),
    )
    total_width_bits: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("total_width_bits", "Total Width", "TotalWidth"),
        description="Data width plus any error correction width",
    )

    @field_validator("size_bytes", mode="before")
    @classmethod
    def size_conformer(cls, value: object) -> object:
        """Convert a "64 GB" style size, or a raw byte count, into bytes."""
        return parse_size(value) if isinstance(value, str) else value

    @field_validator(
        "locator",
        "bank_locator",
        "manufacturer",
        "part_number",
        "serial_number",
        mode="before",
    )
    @classmethod
    def text_conformer(cls, value: object) -> object:
        """Drop placeholder text such as "Unknown" or "Not Specified"."""
        return clean(value) if isinstance(value, str) else value

    @field_validator(
        "speed_mts",
        "configured_speed_mts",
        "rank",
        "data_width_bits",
        "total_width_bits",
        mode="before",
    )
    @classmethod
    def int_conformer(cls, value: object) -> object:
        """Take the number, dropping units such as the "MT/s" of a speed."""
        if not isinstance(value, str):
            return value

        parsed = parse_value(value)
        return parsed[0] if parsed else None

    @field_validator("memory_type", mode="before")
    @classmethod
    def memory_type_conformer(cls, value: object) -> object:
        """Resolve the SMBIOSMemoryType codes that Windows reports."""
        return decode(SMBIOS_MEMORY_TYPES, value) if isinstance(value, str) else value

    @field_validator("form_factor", mode="before")
    @classmethod
    def form_factor_conformer(cls, value: object) -> object:
        """Resolve the FormFactor codes that Windows reports."""
        return decode(WMI_FORM_FACTORS, value) if isinstance(value, str) else value

    @classmethod
    def from_record(cls, record: dict[str, str]) -> Optional["DimmInfo"]:
        """Build a module from a raw dmidecode or wmic record.

        Args:
            record (dict[str, str]): raw field names mapped to their raw values.

        Returns:
            Optional[DimmInfo]: the module, or None if the record describes an
            empty slot or is too malformed to decode.
        """
        try:
            return cls.model_validate(record)
        except ValidationError:
            return None

    @computed_field  # type: ignore[misc]
    @property
    def size(self) -> str:
        """Module capacity as a human readable string, e.g. "64GB"."""
        return format_size(self.size_bytes)

    @override
    def __str__(self) -> str:
        """Describe the module, e.g. "DIMM 0: 64GB DDR5 4800MT/s Micron"."""
        details = [
            detail
            for detail in (
                self.size,
                self.memory_type,
                f"{self.speed_mts}MT/s" if self.speed_mts else None,
                self.manufacturer,
            )
            if detail
        ]
        summary = " ".join(details)
        return f"{self.locator}: {summary}" if self.locator else summary


class DimmDataModel(DataModel):
    """Inventory of the memory modules installed in the system"""

    dimms: list[DimmInfo] = Field(default_factory=list)

    @computed_field  # type: ignore[misc]
    @property
    def dimm_count(self) -> int:
        """Number of populated memory slots."""
        return len(self.dimms)

    @computed_field  # type: ignore[misc]
    @property
    def total_size_bytes(self) -> int:
        """Combined capacity of every populated module, in bytes."""
        return sum(dimm.size_bytes for dimm in self.dimms)

    @computed_field  # type: ignore[misc]
    @property
    def total_size(self) -> str:
        """Combined capacity as a human readable string, e.g. "256GB"."""
        return format_size(self.total_size_bytes)

    @computed_field  # type: ignore[misc]
    @property
    def population(self) -> dict[str, int]:
        """Module count keyed by capacity, smallest capacity first."""
        counts: dict[int, int] = {}
        for dimm in self.dimms:
            counts[dimm.size_bytes] = counts.get(dimm.size_bytes, 0) + 1
        return {format_size(size): count for size, count in sorted(counts.items())}

    @override
    def __str__(self) -> str:
        """Summarise the inventory, e.g. "256GB @ 2 x 64GB 1 x 128GB"."""
        if not self.dimms:
            return "0GB"
        breakdown = " ".join(f"{count} x {size}" for size, count in self.population.items())
        return f"{self.total_size} @ {breakdown}"
