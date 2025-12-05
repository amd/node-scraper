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
from enum import Enum
from typing import (
    Annotated,
    Any,
    ClassVar,
    Dict,
    Generator,
    List,
    Optional,
    TypeVar,
    Union,
)

from pydantic import (
    AfterValidator,
    BaseModel,
    SerializeAsAny,
    field_serializer,
    field_validator,
)

from nodescraper.models import DataModel
from nodescraper.utils import apply_bit_mask_int

AnyCap = TypeVar("AnyCap")


def validate_bdf(bdf: str) -> str:
    """Validate the bus-device-function string format"""
    if not isinstance(bdf, str):
        raise ValueError("BDF must be a string")
    # Shall only contain hex digits, `.`, `:`, and `-`
    if not all(c in "0123456789abcdefABCDEF.-:" for c in bdf):
        raise ValueError("BDF must only contain hex digits, '.', ':', and '-'")
    # TODO: Could add more specific validation for the format, e.g., 00:00.0
    return bdf


BdfStr = Annotated[str, AfterValidator(validate_bdf)]


def field_hex_val_serializer(self, value: Optional[int], _info) -> Optional[str]:
    if value is None:
        return None
    return str(hex(value))


def field_hex_val_validator(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    return int(value, 16)


class CapabilityEnum(Enum):
    """This enum holds the capability IDs for PCI Configuration Space"""

    BASE_REGISTER = 0x00  # Null Capability
    PM = 0x01  # PCI Power Management Interface
    AGP = 0x02  # AGP
    VPD = 0x03  # VPD
    SLOTID = 0x04  # Slot Identification
    MSI = 0x05  # MSI
    COMPACT_PCI_HS = 0x06  # CompactPCI Hot Swap
    PCIX = 0x07  # PCI-X
    HYPERTRANS = 0x08  # HyperTransport
    VENDOR = 0x09  # Vendor-specific
    DEBUG_PORT = 0x0A  # Debug Port
    COMPACT_PCI_CENTRAL = 0x0B  # CompactPCI Central Resource Control
    PCI_HP = 0x0C  # PCI Hot Plug
    PCI_BRIDGE = 0x0D  # PCI Bridge Subsstem ID
    AGP_8X = 0x0E  # AGP 8x y
    SECURE_DEV = 0x0F  # Secure Device
    PCIE_EXP = 0x10  # PCI Express
    MSIX = 0x11  # MSI-X
    SATA = 0x12  # Serial ATA Data/Index
    AF = 0x13  # Advanced Features
    EA = 0x14  # Enhanced Allocation .
    FPB = 0x15  # Flattening Portal Bridge (FPB)


MAX_CAP_ID = max(cap_id.value for cap_id in CapabilityEnum)


class ExtendedCapabilityEnum(Enum):
    """This enum holds the extended capability IDs for PCI Configuration Space"""

    NULL = 0x0000  # Null Capability
    AER = 0x0001  # Advanced Error Reporting Extended
    VCEC = 0x0002  # Virtual Channel Extended Capability
    DSN = 0x0003  # Device Serial Number Extended Capability
    PWR_BUDGET = 0x0004  # Power Budgeting Extended Capability
    LNK_DCLR = 0x0005  # Root Complex Link Declaration Extended Capability
    LNK_CEC = 0x0006  # Root Complex Internal Link Control Extended Capability
    RCECOLL = 0x0007  # Root Complex Event Collector Endpoint Association Extended Capability
    MFVC = 0x0008  # Multi-Function Virtual Channel Extended Capability
    VC2 = 0x0009  # Virtual Channel Extended Capability
    RCRB = 0x000A  # RCRB Header Extended Capability
    VNDR = 0x000B  # Vendor-specific Extended Capability
    CAC = 0x000C  # Configuration Access Correlation Extended Capability
    ACS = 0x000D  # ACS Extended Capability
    ARI = 0x000E  # ARI Extended Capability (ARI)
    ATS = 0x000F  # ATS Extended Capability
    SRIOV = 0x0010  # SR-IOV Extended Capability
    MRIOV = 0x0011  # MR-IOV Extended Capability (MR-IOV) Must not implement.
    MULTCAST = 0x0012  # Multicast Extended Capability
    PAGE_REQ = 0x0013  # Page Request Extended Capability (PRI)
    AMD = 0x0014  # Reserved for AMD
    RBAR = 0x0015  # Resizable BAR Extended Capability
    DPA = 0x0016  # Dynamic Power Allocation Extended Capability (DPA)
    TPH = 0x0017  # TPH Requester Extended Capability
    LTR = (
        0x0018  # LTR Extended Capability . LTR is controlled using Function 0 which is never a VF.
    )
    SPCI = 0x0019  # Secondary PCI Express Extended Capability
    PMUX = 0x001A  # PMUX Extended Capability . PMUX is controlled using Function 0 which is never a VF.
    PASID = 0x001B  # PASID Extended Capability
    LN = 0x001C  # LN Requester Extended Capability (LNR)
    DPC = 0x001D  # DPC Extended Capability.
    L1PM = 0x001E  # L1 PM Substates Extended Capability . L1 PM Substates is controlled using Function 0 which is never a VF.
    PTM = 0x001F  # Precision Time Management Extended Capability (PTM)
    MPCIE = 0x0020  # PCI Express over M-PHY Extended Capability (M-PCIe)
    FRS = 0x0021  # FRS Queueing Extended Capability
    RTR = 0x0022  # Readiness Time Reporting Extended Capability
    DVENDR = 0x0023  # Designated vendor-specific Extended Capability
    VFBAR = 0x0024  # VF Resizable BAR Extended Capability
    DLF = 0x0025  # Data Link Feature Extended Capability .
    PL_16GT = 0x0026  # Physical Layer 16.0 GT/s Extended Capability
    LM = 0x0027  # Lane Margining at the Receiver Extended Capability
    HID = 0x0028  # Hierarchy ID Extended Capability
    NPEM = 0x0029  # Native PCIe Enclosure Management Extended Capability (NPEM)
    PL_32GT = 0x002A  # Physical Layer 32.0 GT/s Extended Capability
    ALT_PROTOCOL = 0x002B  # Alternate Protocol Extended Capability
    SFI = 0x002C  # System Firmware Intermediary (SFI)Extended Capability
    DOE = 0x2E  # 	0x2e	 Data Object Exchange
    INT_DOE = 0x30  # 	0x30	Integrity and Data Encryption


MAX_ECAP_ID = max(cap_id.value for cap_id in ExtendedCapabilityEnum)


class PcieBitField(BaseModel):
    """Holds data about a bit field including bit_mask and description and a method to get its value"""

    bit_mask: int
    desc: str
    val: Optional[int] = None

    def set_val(self, reg_val: Optional[int]):
        """This will apply the bitmask and shift the value to get the bit field value"""
        if reg_val is None:
            self.val = None
        else:
            self.val = apply_bit_mask_int(reg_val, self.bit_mask)

    def get_val(self) -> Optional[int]:
        """Returns the value of the bit field"""
        return self.val

    def apply_mask(self, reg_val) -> Optional[int]:
        """This will apply the bitmask and shift the value to get the bit field value
        Ex: reg_val = 0x1200, bit_mask = 0xFF00, then the value of the bit field is 0x1200 & 0xFF00 -> 0x1200 >> 8 -> 0x12
        """
        if reg_val is None:
            return None
        else:
            return apply_bit_mask_int(reg_val, self.bit_mask)

    validate_val = field_validator("val", mode="before")(field_hex_val_validator)
    serialize_val = field_serializer("val")(field_hex_val_serializer)


class PcieRegister(BaseModel):
    """Holds data about a register including its position, width, value, bit fields and a method to get the value of a bit field
    setpci_name is the name of the register in setpci output --dumpregs"""

    width: int
    offset: int
    val: Optional[int] = None
    desc: str = ""
    err: Optional[str] = None

    def iter_fields(self) -> Generator[tuple[str, PcieBitField], Any, None]:
        """Iterator for bit fields in the register"""
        for name, value in iter(self):
            if isinstance(value, PcieBitField):
                yield name, value

    @property
    def bit_fields(self) -> dict[str, PcieBitField]:
        """Get all the bit fields in the register"""
        return {name: value for name, value in self.iter_fields()}

    # This will serialize the value of the register as hex
    serialize_val = field_serializer("val")(field_hex_val_serializer)

    # This will validate the value of the register from hex to int
    validate_val = field_validator("val", mode="before")(field_hex_val_validator)

    def __setattr__(self, name, value):
        """When the value of the register is set, set all the bit fields in the register automatically
        otherwise just set the value"""
        if name == "val":
            # set all .vals in all bitfields
            for _, field in self.iter_fields():
                field.set_val(value)
        super().__setattr__(name, value)


class PcieCapStructure(BaseModel):
    """Holds the capability and extended capability info including the ID and description as well as
    the registers that exists within that capability structure."""

    cap_id: ClassVar[Enum]
    desc: str
    offset: int = 0
    extended: Optional[bool] = False

    def iter_regs(self) -> Generator[tuple[str, PcieRegister], Any, None]:
        """Iterator for bit fields in the register"""
        for name, value in iter(self):
            if isinstance(value, PcieRegister):
                yield name, value

    def set_regs(self, values: Dict[str, int]):
        for name, value in iter(self):
            if isinstance(value, PcieRegister):
                value.val = values.get(name, None)

    def null_err_regs(self, filters: Optional[List[str]] = None):
        """Set all registers to None, except those in the filters list"""
        err_null = []
        for name, reg in self.iter_regs():
            if filters is not None:
                if name in filters and (reg.val is None or reg.err is not None):
                    err_null.append(name)
            elif filters is None:
                if reg.val is None or reg.err is not None:
                    err_null.append(name)
        return err_null


def cap_id_to_class(
    cap_id: Union[CapabilityEnum, ExtendedCapabilityEnum],
) -> Optional[type[PcieCapStructure]]:
    """Convert a generic PcieCapStructure to a Specific PcieCapStructure based on the cap_id

    Parameters
    ----------
    cap_id : Union[CapabilityEnum, ExtendedCapabilityEnum]
        A capability ID

    Returns
    -------
    Optional[type[PcieCapStructure]]
        A specific PcieCapStructure class or None if not found
    """
    for cls in PcieCapStructure.__subclasses__():
        if cls.cap_id == cap_id:
            return cls
    return None


class CommandRegister(PcieRegister):
    """Command Register in PCI Configuration Space"""

    offset: int = 0x04
    width: int = 16
    io_space_en: PcieBitField = PcieBitField(bit_mask=0x1, desc="I/O Space Enable")
    mem_space_en: PcieBitField = PcieBitField(bit_mask=0x2, desc="Memory Space Enable")
    bus_mstr_en: PcieBitField = PcieBitField(bit_mask=0x4, desc="Bus Master Enable")
    spec_cyc_en: PcieBitField = PcieBitField(bit_mask=0x8, desc="Special Cycle Enable")
    mem_wr_inval: PcieBitField = PcieBitField(bit_mask=0x10, desc="Memory Write and Invalidate")
    vga_pal_snoop: PcieBitField = PcieBitField(bit_mask=0x20, desc="VGA Palette Snoop")
    parity_err_res: PcieBitField = PcieBitField(bit_mask=0x40, desc="Parity Error Response")
    idsel_step_wait_cyc_ctrl: PcieBitField = PcieBitField(
        bit_mask=0x80, desc="IDSEL Stepping/Wait Cycle Control"
    )
    serr_en: PcieBitField = PcieBitField(bit_mask=0x100, desc="SERR# Enable")
    fast_b2b_trans_en: PcieBitField = PcieBitField(
        bit_mask=0x200, desc="Fast Back-to-Back Transactions Enable"
    )
    int_dis: PcieBitField = PcieBitField(bit_mask=0x400, desc="Interrupt Disable")


class StatusRegister(PcieRegister):
    """Status Register in PCI Configuration Space"""

    offset: int = 0x06
    width: int = 16
    desc: str = "Status Register"
    immed_readiness: PcieBitField = PcieBitField(bit_mask=(1 << 0), desc="Immediate Readiness")
    int_stat: PcieBitField = PcieBitField(bit_mask=(1 << 3), desc="Interrupt Status")
    cap_list: PcieBitField = PcieBitField(bit_mask=(1 << 4), desc="Capabilities List")
    sixty_six_mhz_cap: PcieBitField = PcieBitField(bit_mask=(1 << 5), desc="66 MHz Capable")
    fast_b2b_trans_cap: PcieBitField = PcieBitField(
        bit_mask=(1 << 7), desc="Fast Back-to-Back Transactions Capable"
    )
    mstr_data_par_err: PcieBitField = PcieBitField(
        bit_mask=(1 << 8), desc="Master Data Parity Error"
    )
    devsel_timing: PcieBitField = PcieBitField(bit_mask=(0b11 << 9), desc="DEVSEL Timing")
    signaled_target_abort: PcieBitField = PcieBitField(
        bit_mask=(1 << 11), desc="Signaled Target Abort"
    )
    rcvd_target_abort: PcieBitField = PcieBitField(bit_mask=(1 << 12), desc="Received Target Abort")
    rcvd_mstr_abort: PcieBitField = PcieBitField(bit_mask=(1 << 13), desc="Received Master Abort")
    signaled_sys_err: PcieBitField = PcieBitField(bit_mask=(1 << 14), desc="Signaled System Error")
    det_parity_err: PcieBitField = PcieBitField(bit_mask=(1 << 15), desc="Detected Parity Error")


class Type01Common(PcieCapStructure):
    """Common fields for Type 01"""

    cap_id: ClassVar[Enum] = CapabilityEnum.BASE_REGISTER
    desc: str = "Type 0/1 Common Configuration Space"
    vendor_id: PcieRegister = PcieRegister(width=16, offset=0x00)
    device_id: PcieRegister = PcieRegister(width=16, offset=0x02)
    command: CommandRegister = CommandRegister()
    status: StatusRegister = StatusRegister()
    revision_id: PcieRegister = PcieRegister(width=8, offset=0x08)
    prog_if: PcieRegister = PcieRegister(width=8, offset=0x09)
    subclass: PcieRegister = PcieRegister(width=8, offset=0x0A)
    class_code: PcieRegister = PcieRegister(width=8, offset=0x0B)
    cache_line_size: PcieRegister = PcieRegister(width=8, offset=0x0C)
    latency_timer: PcieRegister = PcieRegister(width=8, offset=0x0D)
    header_type: PcieRegister = PcieRegister(width=8, offset=0x0E)
    bist: PcieRegister = PcieRegister(width=8, offset=0x0F)


class Type0Configuration(Type01Common):
    """Type 0 Specific Common Configuration Space"""

    cap_id: ClassVar[Enum] = CapabilityEnum.BASE_REGISTER
    desc: str = "Type 0 Specific Common Configuration Space"
    base_address_0: PcieRegister = PcieRegister(
        offset=0x10,
        width=32,
        desc="7.5.1.2.1 Base Address Registers (Offset 10h - 24h) / 7.5.1.3.1 Type 1 Base Address Registers (Offset 10h-14h)",
    )
    base_address_1: PcieRegister = PcieRegister(
        offset=0x14,
        width=32,
        desc="7.5.1.2.1 Base Address Registers (Offset 10h - 24h) / 7.5.1.3.1 Type 1 Base Address Registers (Offset 10h-14h)",
    )
    base_address_2: PcieRegister = PcieRegister(
        offset=0x18,
        width=32,
        desc="7.5.1.2.1 Base Address Registers (Offset 10h - 24h)",
    )
    base_address_3: PcieRegister = PcieRegister(
        offset=0x1C,
        width=32,
        desc="7.5.1.2.1 Base Address Registers (Offset 10h - 24h)",
    )
    base_address_4: PcieRegister = PcieRegister(
        offset=0x20,
        width=32,
        desc="7.5.1.2.1 Base Address Registers (Offset 10h - 24h)",
    )
    base_address_5: PcieRegister = PcieRegister(
        offset=0x24,
        width=32,
        desc="7.5.1.2.1 Base Address Registers (Offset 10h - 24h)",
    )
    cardbus_cis: PcieRegister = PcieRegister(
        offset=0x28,
        width=32,
        desc="7.5.1.2.2 Cardbus CIS Pointer Register (Offset 28h)",
    )
    subsystem_vendor_id: PcieRegister = PcieRegister(
        offset=0x2C,
        width=16,
        desc="7.5.1.2.3 Subsystem Vendor ID Register/Subsystem ID Register (Offset 2Ch/2Eh)",
    )
    subsystem_id: PcieRegister = PcieRegister(
        offset=0x2E,
        width=16,
        desc="7.5.1.2.3 Subsystem Vendor ID Register/Subsystem ID Register (Offset 2Ch/2Eh)",
    )
    rom_address: PcieRegister = PcieRegister(
        offset=0x30,
        width=32,
        desc="7.5.1.2.4 Expansion ROM Base Address Register (Offset 30h)",
    )
    min_gnt: PcieRegister = PcieRegister(
        offset=0x3E,
        width=8,
        desc="7.5.1.2.5 Min_Gnt Register/Max_Lat Register (Offset 3Eh/3Fh)",
    )
    max_lat: PcieRegister = PcieRegister(
        offset=0x3F,
        width=8,
        desc="7.5.1.2.5 Min_Gnt Register/Max_Lat Register (Offset 3Eh/3Fh)",
    )


class SecStatusRegister(PcieRegister):
    """Sec Status reg for Type 1"""

    offset: int = 0x1E
    width: int = 16
    desc: str = "Secondary Status Register"
    sixty_six_mhz_cap: PcieBitField = PcieBitField(bit_mask=(1 << 5), desc="66 MHz Capable")
    fast_b2b_trans_cap: PcieBitField = PcieBitField(
        bit_mask=(1 << 7), desc="Fast Back-to-Back Transactions Capable"
    )
    mstr_data_par_err: PcieBitField = PcieBitField(
        bit_mask=(1 << 8), desc="Master Data Parity Error"
    )
    devsel_timing: PcieBitField = PcieBitField(bit_mask=(0b11 << 9), desc="DEVSEL Timing")
    signaled_target_abort: PcieBitField = PcieBitField(
        bit_mask=(1 << 11), desc="Signaled Target Abort"
    )
    rcvd_target_abort: PcieBitField = PcieBitField(bit_mask=(1 << 12), desc="Received Target Abort")
    rcvd_mstr_abort: PcieBitField = PcieBitField(bit_mask=(1 << 13), desc="Received Master Abort")
    rcvd_sys_err: PcieBitField = PcieBitField(bit_mask=(1 << 14), desc="Received System Error")
    det_parity_err: PcieBitField = PcieBitField(bit_mask=(1 << 15), desc="Detected Parity Error")


class BridgeControlRegister(PcieRegister):
    """Bridge controller register Specific to Type 1"""

    offset: int = 0x3E
    width: int = 16
    desc: str = "7.5.1.3.13 Bridge Control Register (Offset 3Eh)"
    parity_err_res_en: PcieBitField = PcieBitField(
        bit_mask=(1 << 0), desc="Parity Error Response Enable"
    )
    serr_en: PcieBitField = PcieBitField(bit_mask=(1 << 1), desc="SERR# Enable")
    isa_en: PcieBitField = PcieBitField(bit_mask=(1 << 2), desc="ISA Enable")
    vga_en: PcieBitField = PcieBitField(bit_mask=(1 << 3), desc="VGA Enable")
    vga_16_bit_dec: PcieBitField = PcieBitField(bit_mask=(1 << 4), desc="VGA 16-bit Decode")
    mstr_abort_mode: PcieBitField = PcieBitField(bit_mask=(1 << 5), desc="Master Abort Mode")
    sec_bus_rst: PcieBitField = PcieBitField(bit_mask=(1 << 6), desc="Secondary Bus Reset")
    fast_b2b_trans_en: PcieBitField = PcieBitField(
        bit_mask=(1 << 7), desc="Fast Back-to-Back Transactions Enable"
    )
    primary_discard_timer: PcieBitField = PcieBitField(
        bit_mask=(1 << 8), desc="Primary Discard Timer"
    )
    sec_discard_timer: PcieBitField = PcieBitField(
        bit_mask=(1 << 9), desc="Secondary Discard Timer"
    )
    discard_timer_stat: PcieBitField = PcieBitField(bit_mask=(1 << 10), desc="Discard Timer Status")
    discard_timer_serr_en: PcieBitField = PcieBitField(
        bit_mask=(1 << 11), desc="Discard Timer SERR# Enable"
    )


class Type1Configuration(Type01Common):
    """Type 1 Specific Common Configuration Space"""

    cap_id: ClassVar[Enum] = CapabilityEnum.BASE_REGISTER
    desc: str = "Type 1 Specific Common Configuration Space"
    PRIMARY_BUS: PcieRegister = PcieRegister(
        offset=0x18, width=8, desc="7.5.1.3.2 Primary Bus Number Register (Offset 18h)"
    )
    SECONDARY_BUS: PcieRegister = PcieRegister(
        offset=0x19,
        width=8,
        desc="7.5.1.3.3 Secondary Bus Number Register (Offset 19h)",
    )
    SUBORDINATE_BUS: PcieRegister = PcieRegister(
        offset=0x1A,
        width=8,
        desc="7.5.1.3.4 Subordinate Bus Number Register (Offset 1Ah)",
    )
    SEC_LATENCY_TIMER: PcieRegister = PcieRegister(
        offset=0x1B, width=8, desc="7.5.1.3.5 Secondary Latency Timer (Offset 1Bh)"
    )
    IO_BASE: PcieRegister = PcieRegister(
        offset=0x1C,
        width=8,
        desc="7.5.1.3.6 I/O Base/I/O Limit Registers(Offset 1Ch/1Dh)",
    )
    IO_LIMIT: PcieRegister = PcieRegister(
        offset=0x1D,
        width=8,
        desc="7.5.1.3.6 I/O Base/I/O Limit Registers(Offset 1Ch/1Dh)",
    )
    MEMORY_BASE: PcieRegister = PcieRegister(
        offset=0x20,
        width=16,
        desc="7.5.1.3.8 Memory Base Register/Memory Limit Register(Offset 20h/22h)",
    )
    MEMORY_LIMIT: PcieRegister = PcieRegister(
        offset=0x22,
        width=16,
        desc="7.5.1.3.8 Memory Base Register/Memory Limit Register(Offset 20h/22h)",
    )
    PREF_MEMORY_BASE: PcieRegister = PcieRegister(
        offset=0x24,
        width=16,
        desc="7.5.1.3.9 Prefetchable Memory Base/Prefetchable Memory Limit Registers (Offset 24h/26h)",
    )
    PREF_MEMORY_LIMIT: PcieRegister = PcieRegister(
        offset=0x26,
        width=16,
        desc="7.5.1.3.9 Prefetchable Memory Base/Prefetchable Memory Limit Registers (Offset 24h/26h)",
    )
    PREF_BASE_UPPER32: PcieRegister = PcieRegister(
        offset=0x28,
        width=32,
        desc="7.5.1.3.10 Prefetchable Base Upper 32 Bits/Prefetchable Limit Upper 32 Bits Registers (Offset 28h/2Ch)",
    )
    PREF_LIMIT_UPPER32: PcieRegister = PcieRegister(
        offset=0x2C,
        width=32,
        desc="7.5.1.3.10 Prefetchable Base Upper 32 Bits/Prefetchable Limit Upper 32 Bits Registers (Offset 28h/2Ch)",
    )
    IO_BASE_UPPER16: PcieRegister = PcieRegister(
        offset=0x30,
        width=16,
        desc="7.5.1.3.11 I/O Base Upper 16 Bits/I/O Limit Upper 16 Bits Registers (Offset 30h/32h)",
    )
    IO_LIMIT_UPPER16: PcieRegister = PcieRegister(
        offset=0x32,
        width=16,
        desc="7.5.1.3.11 I/O Base Upper 16 Bits/I/O Limit Upper 16 Bits Registers (Offset 30h/32h)",
    )
    BRIDGE_ROM_ADDRESS: PcieRegister = PcieRegister(
        offset=0x38,
        width=32,
        desc="7.5.1.3.12 Expansion ROM Base Address Register (Offset 38h)",
    )


class CapPm(PcieCapStructure):
    """Capability Structure for Power Management"""

    cap_id: ClassVar[Enum] = CapabilityEnum.PM
    desc: str = "PCI Power Management Interface (9.6 SR-IOV Power Management)"


class CapAgp(PcieCapStructure):
    """Capability Structure for Accelerated Graphics Port"""

    cap_id: ClassVar[Enum] = CapabilityEnum.AGP
    desc: str = ""


class CapVpd(PcieCapStructure):
    """Capability Structure for Virtual Product Data"""

    cap_id: ClassVar[Enum] = CapabilityEnum.VPD
    desc: str = "VPD (9.3.6.1 VPD Capability)"


class CapSlotid(PcieCapStructure):
    """Capability Structure for Slot Identification"""

    cap_id: ClassVar[Enum] = CapabilityEnum.SLOTID
    desc: str = "Slot Identification"


class CapMsi(PcieCapStructure):
    """Capability Structure for Message Signaled Interrupts"""

    cap_id: ClassVar[Enum] = CapabilityEnum.MSI
    desc: str = "7.7.1 MSI Capability Structures"


class CapCompatHotSwp(PcieCapStructure):
    """Cap for CompactPCI Hot Swap"""

    cap_id: ClassVar[Enum] = CapabilityEnum.COMPACT_PCI_HS
    desc: str = "CompactPCI Hot Swap"


class CapPcix(PcieCapStructure):
    """Cap for PCI Extensions"""

    cap_id: ClassVar[Enum] = CapabilityEnum.PCIX
    desc: str = "PCI-X"


class CapHt(PcieCapStructure):
    """HyperTransport Capability"""

    cap_id: ClassVar[Enum] = CapabilityEnum.HYPERTRANS
    desc: str = "HyperTransport"


class CapVndr(PcieCapStructure):
    """Vendor Specific Capability"""

    cap_id: ClassVar[Enum] = CapabilityEnum.VENDOR
    desc: str = "7.9.4 Vendor-Specific Capability"


class CapDbg(PcieCapStructure):
    """Capability for Debug Port"""

    cap_id: ClassVar[Enum] = CapabilityEnum.DEBUG_PORT
    desc: str = "Debug Port"


class CapCompatPcieCentral(PcieCapStructure):
    """Capability for CompactPCI Central Resource Control"""

    cap_id: ClassVar[Enum] = CapabilityEnum.COMPACT_PCI_CENTRAL
    desc: str = "CompactPCI Central Resource Control"


class CapHotplug(PcieCapStructure):
    """Capability for PCI Hot Plug"""

    cap_id: ClassVar[Enum] = CapabilityEnum.PCI_HP
    desc: str = "PCI Hot Plug"


class CapPciBridge(PcieCapStructure):
    """Capability for PCI Bridge Subsystem ID"""

    cap_id: ClassVar[Enum] = CapabilityEnum.PCI_BRIDGE
    desc: str = "7.9.24 Subsystem ID and Sybsystem Vendor ID Capability"


class CapEnhAgp(PcieCapStructure):
    """Enhanced Accelerated Graphics Port (AGP) interface supporting 8x data rate."""

    cap_id: ClassVar[Enum] = CapabilityEnum.AGP
    desc: str = "AGP 8x"


class CapSecure(PcieCapStructure):
    """Secure Device Capability"""

    cap_id: ClassVar[Enum] = CapabilityEnum.SECURE_DEV
    desc: str = "Secure Device"


class PcieCapListReg(PcieRegister):
    offset: int = 0x00
    width: int = 16
    cap_id_desc: PcieBitField = PcieBitField(bit_mask=0x00FF, desc="Capability ID")
    nxt_cap_ptr: PcieBitField = PcieBitField(bit_mask=0xFF00, desc="Next Capability Pointer")


class DevCtrlRegister(PcieRegister):
    offset: int = 0x08
    width: int = 16
    desc: str = "7.5.3.4 Device Control Register (Offset 08h)"
    corr_err_report_en: PcieBitField = PcieBitField(
        bit_mask=(1 << 0), desc="Correctable Error Enable"
    )
    non_fatal_err_report_en: PcieBitField = PcieBitField(
        bit_mask=(1 << 1), desc="Non-fatal Error Reporting Enable"
    )
    fatal_err_report_en: PcieBitField = PcieBitField(
        bit_mask=(1 << 2), desc="Fatal Error Reporting Enable"
    )
    ur_report_en: PcieBitField = PcieBitField(
        bit_mask=(1 << 3), desc="Unsupported Request Reporting Enable"
    )
    en_relaxed_order: PcieBitField = PcieBitField(bit_mask=(1 << 4), desc="Enable Relaxed Ordering")
    mps: PcieBitField = PcieBitField(bit_mask=(0x7 << 5), desc="Max_Payload_Size")
    ext_tag_field_en: PcieBitField = PcieBitField(
        bit_mask=(1 << 8), desc="Extended Tag Field Enable"
    )
    phantom_func_en: PcieBitField = PcieBitField(bit_mask=(1 << 9), desc="Phantom Functions Enable")
    aux_pwr_pm_en: PcieBitField = PcieBitField(bit_mask=(1 << 10), desc="Aux Power PM Enable")
    en_no_snoop: PcieBitField = PcieBitField(bit_mask=(1 << 11), desc="Enable No Snoop")
    max_rd_req_size: PcieBitField = PcieBitField(bit_mask=(0x7 << 12), desc="Max_Read_Request_Size")
    bridge_cfg_retry_en_init_func_lvl_rst: PcieBitField = PcieBitField(
        bit_mask=(1 << 15),
        desc="Bridge Configuration Retry Enable / Initiate Function Level Reset",
    )


class DevStatRegister(PcieRegister):
    offset: int = 0x0A
    width: int = 16
    desc: str = "Device Status Register"
    corr_err_det: PcieBitField = PcieBitField(bit_mask=(1 << 0), desc="Correctable Error Detected")
    non_fatal_err_det: PcieBitField = PcieBitField(
        bit_mask=(1 << 1), desc="Non-Fatal Error Detected"
    )
    fatal_err_det: PcieBitField = PcieBitField(bit_mask=(1 << 2), desc="Fatal Error Detected")
    ur_det: PcieBitField = PcieBitField(bit_mask=(1 << 3), desc="Unsupported Request Detected")
    aux_pwr_det: PcieBitField = PcieBitField(bit_mask=(1 << 4), desc="AUX Power Detected")
    trans_pending: PcieBitField = PcieBitField(bit_mask=(1 << 5), desc="Transactions Pending")
    emer_pwr_reduction_det: PcieBitField = PcieBitField(
        bit_mask=(1 << 6), desc="Emergency Power Reduction Detected"
    )


class LinkCapRegister(PcieRegister):
    offset: int = 0x0C
    width: int = 32
    desc: str = "7.5.3.6 Link Capabilities Register (Offset 0Ch)"
    max_lnk_speed: PcieBitField = PcieBitField(bit_mask=(0xF << 0), desc="Max Link Speed")
    max_lnk_width: PcieBitField = PcieBitField(bit_mask=(0x3F << 4), desc="Maximum Link Width")
    aspm_support: PcieBitField = PcieBitField(bit_mask=(0x3 << 10), desc="ASPM Support")
    l0s_exit_lat: PcieBitField = PcieBitField(bit_mask=(0x7 << 12), desc="L0s Exit Latency")
    l1_exit_lat: PcieBitField = PcieBitField(bit_mask=(0x7 << 15), desc="L1 Exit Latency")
    clk_pwr_mgmt: PcieBitField = PcieBitField(bit_mask=(1 << 18), desc="Clock Power Management")
    surprise_dn_err_report_cap: PcieBitField = PcieBitField(
        bit_mask=(1 << 19), desc="Surprise Down Error Reporting Capable"
    )
    dll_lnk_active_report_cap: PcieBitField = PcieBitField(
        bit_mask=(1 << 20), desc="Data Link Layer Link Active Reporting Capable"
    )
    lnk_bw_notif_cap: PcieBitField = PcieBitField(
        bit_mask=(1 << 21), desc="Link Bandwidth Notification Capability"
    )
    aspm_optionality_comp: PcieBitField = PcieBitField(
        bit_mask=(1 << 22), desc="ASPM Optionality Compliance"
    )
    port_num: PcieBitField = PcieBitField(bit_mask=(0xFF << 24), desc="Port Number")


class LinkStatRegister(PcieRegister):
    """Link stat for Type 1"""

    offset: int = 0x12
    width: int = 16
    desc: str = "Link Status Register"
    curr_lnk_speed: PcieBitField = PcieBitField(bit_mask=(0b1111 << 0), desc="Current Link Speed")
    neg_lnk_width: PcieBitField = PcieBitField(
        bit_mask=(0b111111 << 4), desc="Negotiated Link Width"
    )
    lnk_training: PcieBitField = PcieBitField(bit_mask=(1 << 11), desc="Link Training")
    slot_clk_cfg: PcieBitField = PcieBitField(bit_mask=(1 << 12), desc="Slot Clock Configuration")
    dll_lnk_active: PcieBitField = PcieBitField(
        bit_mask=(1 << 13), desc="Data Link Layer Link Active"
    )
    lnk_bw_mgmt_stat: PcieBitField = PcieBitField(
        bit_mask=(1 << 14), desc="Link Bandwidth Management Status"
    )
    lnk_auto_bw_stat: PcieBitField = PcieBitField(
        bit_mask=(1 << 15), desc="Link Autonomous Bandwidth Status"
    )


class DevCtrl2Register(PcieRegister):
    offset: int = 0x28
    width: int = 16
    desc: str = "7.5.3.16 Device Control 2 Register (Offset 28h)"
    completion_timeout_val: PcieBitField = PcieBitField(
        bit_mask=(0xF << 0), desc="Completion Timeout Value"
    )
    completion_timeout_dis: PcieBitField = PcieBitField(
        bit_mask=(1 << 4), desc="Completion Timeout Disable"
    )
    ari_forward_en: PcieBitField = PcieBitField(bit_mask=(1 << 5), desc="ARI Forwarding Enable")
    atomic_op_req_en: PcieBitField = PcieBitField(bit_mask=(1 << 6), desc="AtomicOp Request Enable")
    atomic_op_egress_blk: PcieBitField = PcieBitField(
        bit_mask=(1 << 7), desc="AtomicOp Egress Blocking"
    )
    ido_req_en: PcieBitField = PcieBitField(bit_mask=(1 << 8), desc="IDO Request Enable")
    ido_completion_en: PcieBitField = PcieBitField(bit_mask=(1 << 9), desc="IDO Completion Enable")
    ltr_mechanism_en: PcieBitField = PcieBitField(bit_mask=(1 << 10), desc="LTR Mechanism Enable")
    emergency_pwr_reduction_en: PcieBitField = PcieBitField(
        bit_mask=(1 << 11), desc="Emergency Power Reduction Enable"
    )
    ten_bit_tag_req_en: PcieBitField = PcieBitField(
        bit_mask=(1 << 12), desc="10-bit Tag Request Enable"
    )
    obff_en: PcieBitField = PcieBitField(bit_mask=(0x3 << 13), desc="OBFF Enable")
    end_end_tlp_prefix_blk: PcieBitField = PcieBitField(
        bit_mask=(1 << 15), desc="End-End TLP Prefix Blocking"
    )


class LinkCap2Register(PcieRegister):
    """Link cap 2 for Type 1"""

    offset: int = 0x2C
    width: int = 32
    desc: str = "7.5.3.18 Link Capabilities 2 Register (Offset 2Ch)"
    supported_lnk_speed_vec: PcieBitField = PcieBitField(
        bit_mask=(0b111111 << 1), desc="Supported Link Speeds Vector"
    )
    xlnk_supported: PcieBitField = PcieBitField(bit_mask=(1 << 8), desc="Crosslink Supported")
    lower_skp_os_gen_supported_speeds_vec: PcieBitField = PcieBitField(
        bit_mask=(0b111111 << 9), desc="Lower SKP OS Generation Supported Speeds Vector"
    )
    lower_skip_os_rec_supported_speeds_vec: PcieBitField = PcieBitField(
        bit_mask=(0b111111 << 16), desc="Lower SKP OS Reception Supported Speeds Vector"
    )
    retimer_prsnc_det_supported: PcieBitField = PcieBitField(
        bit_mask=(1 << 23), desc="Retimer Presence Detect Supported"
    )
    two_retimers_prsnc_det_supported: PcieBitField = PcieBitField(
        bit_mask=(1 << 24), desc="Two Retimers Presence Detect Supported"
    )
    drs_supported: PcieBitField = PcieBitField(bit_mask=(1 << 31), desc="DRS Supported")


class PcieExp(PcieCapStructure):
    """PCIE Express Capability Structure 7.5.3 PCI Express Capability Structure

    This structure allows identification of a PCI Express device Function
    and indicates support for new PCI Express features.
    """

    cap_id: ClassVar[Enum] = CapabilityEnum.PCIE_EXP
    desc: str = "7.5.3 PCI Express Capability Structure"
    cap_list: PcieCapListReg = PcieCapListReg()
    pcie_cap_reg: PcieRegister = PcieRegister(
        offset=2,
        width=16,
        desc="7.5.3.2 PCI Express Capabilities Register (Offset 02h)",
    )
    dev_cap_reg: PcieRegister = PcieRegister(
        offset=0x4, width=32, desc="7.5.3.3 Device Capabilities Register (Offset 04h)"
    )
    dev_ctrl_reg: DevCtrlRegister = DevCtrlRegister()
    dev_stat_reg: DevStatRegister = DevStatRegister()
    lnk_cap_reg: LinkCapRegister = LinkCapRegister()
    lnk_ctrl_reg: PcieRegister = PcieRegister(
        offset=0x10, width=16, desc="7.5.3.7 Link Control Register (Offset 10h)"
    )
    lnk_stat_reg: LinkStatRegister = LinkStatRegister()
    dev_ctrl_2_reg: DevCtrl2Register = DevCtrl2Register()
    lnk_cap_2_reg: LinkCap2Register = LinkCap2Register()


class CapMSIX(PcieCapStructure):
    """Capability Structure for MSI-X"""

    cap_id: ClassVar[Enum] = CapabilityEnum.MSIX
    offset: int = 0x00
    desc: str = "7.7.2 MSI-X Capability and Table Structure"


class CapSATA(PcieCapStructure):
    """Cap for Serial ATA Data/Index Configuration"""

    cap_id: ClassVar[Enum] = CapabilityEnum.SATA
    offset: int = 0x00
    desc: str = "Serial ATA Data/Index Configuration"


class CapAF(PcieCapStructure):
    """Capability for Advanced Features"""

    cap_id: ClassVar[Enum] = CapabilityEnum.AF
    offset: int = 0x00
    desc: str = "7.9.22 Conventional PCI Advanced Features Capability (AF)"


class CapEA(PcieCapStructure):
    """Capability for Enhanced Allocation"""

    cap_id: ClassVar[Enum] = CapabilityEnum.EA
    offset: int = 0x00
    desc: str = "7.8.5 Enhanced Allocation Capability Structure (EA)"


class AerEcapHdr(PcieRegister):
    """Capability for Advanced Error Reporting"""

    offset: int = 0x00
    width: int = 32
    desc: str = "7.8.4.1 Advanced Error Reporting Extended Capability Header (Offset 00h)"
    pcie_eacp_id: PcieBitField = PcieBitField(
        bit_mask=0x0000FFFF, desc="PCI Express Extended Capability ID"
    )
    cap_ver: PcieBitField = PcieBitField(bit_mask=0x000F0000, desc="Capability Version")
    nxt_cap_offset: PcieBitField = PcieBitField(bit_mask=0xFFF00000, desc="Next Capability Offset")


class UncorrErrStatReg(PcieRegister):
    """AER register for Uncorrectable Error Status Register"""

    offset: int = 0x04
    width: int = 32
    desc: str = "Uncorrectable Error Status Register"
    dlnk_protocol_err_stat: PcieBitField = PcieBitField(
        bit_mask=(1 << 4), desc="Data Link Protocol Error Status"
    )
    surprise_dn_err_stat: PcieBitField = PcieBitField(
        bit_mask=(1 << 5), desc="Surprise Down Error Status"
    )
    poisoned_tlp_rcvd: PcieBitField = PcieBitField(bit_mask=(1 << 12), desc="Poisoned TLP Received")
    fc_proto_err_stat: PcieBitField = PcieBitField(
        bit_mask=(1 << 13), desc="Flow Control Protocol Error Status"
    )
    cpl_timeout_stat: PcieBitField = PcieBitField(
        bit_mask=(1 << 14), desc="Completion Timeout Status"
    )
    ca_stat: PcieBitField = PcieBitField(bit_mask=(1 << 15), desc="Completer Abort Status")
    unexp_cpl_stat: PcieBitField = PcieBitField(
        bit_mask=(1 << 16), desc="Unexpected Completion Status"
    )
    rx_overflow_stat: PcieBitField = PcieBitField(
        bit_mask=(1 << 17), desc="Receiver Overflow Status"
    )
    malformed_tlp_stat: PcieBitField = PcieBitField(bit_mask=(1 << 18), desc="Malformed TLP Status")
    ecrc_err_stat: PcieBitField = PcieBitField(bit_mask=(1 << 19), desc="ECRC Error Status")
    ur_err_stat: PcieBitField = PcieBitField(
        bit_mask=(1 << 20), desc="Unsupported Request Error Status"
    )
    acs_violation_stat: PcieBitField = PcieBitField(bit_mask=(1 << 21), desc="ACS Violation Status")
    uncorr_int_err_stat: PcieBitField = PcieBitField(
        bit_mask=(1 << 22), desc="Uncorrectable Internal Error Status"
    )
    mc_blocked_tlp_stat: PcieBitField = PcieBitField(
        bit_mask=(1 << 23), desc="MC Blocked TLP Status"
    )
    atomicop_egress_blk_stat: PcieBitField = PcieBitField(
        bit_mask=(1 << 24), desc="AtomicOp Egress Blocked Status"
    )
    tlp_prefix_blk_err_stat: PcieBitField = PcieBitField(
        bit_mask=(1 << 25), desc="TLP Prefix Blocked Error Status"
    )
    poisoned_tlp_egress_blk_stat: PcieBitField = PcieBitField(
        bit_mask=(1 << 26), desc="Poisoned TLP Egress Blocked Status"
    )


class UncorrErrMaskReg(PcieRegister):
    """AER register for Uncorrectable Error Mask Register"""

    offset: int = 0x08
    width: int = 32
    desc: str = "7.8.4.3 Uncorrectable Error Mask Register (Offset 08h)"
    dlnk_protocol_err_mask: PcieBitField = PcieBitField(
        bit_mask=(1 << 4), desc="Data Link Protocol Error Mask"
    )
    surprise_dn_err_mask: PcieBitField = PcieBitField(
        bit_mask=(1 << 5), desc="Surprise Down Error Mask"
    )
    poisoned_tlp_rcvd_mask: PcieBitField = PcieBitField(
        bit_mask=(1 << 12), desc="Poisoned TLP Received Mask"
    )
    fc_proto_err_mask: PcieBitField = PcieBitField(
        bit_mask=(1 << 13), desc="Flow Control Protocol Error Mask"
    )
    cpl_timeout_mask: PcieBitField = PcieBitField(
        bit_mask=(1 << 14), desc="Completion Timeout Mask"
    )
    ca_mask: PcieBitField = PcieBitField(bit_mask=(1 << 15), desc="Completer Abort Mask")
    unexp_cpl_mask: PcieBitField = PcieBitField(
        bit_mask=(1 << 16), desc="Unexpected Completion Mask"
    )
    rx_overflow_mask: PcieBitField = PcieBitField(bit_mask=(1 << 17), desc="Receiver Overflow Mask")
    malformed_tlp_mask: PcieBitField = PcieBitField(bit_mask=(1 << 18), desc="Malformed TLP Mask")
    ecrc_err_mask: PcieBitField = PcieBitField(bit_mask=(1 << 19), desc="ECRC Error Mask")
    ur_err_mask: PcieBitField = PcieBitField(
        bit_mask=(1 << 20), desc="Unsupported Request Error Mask"
    )
    acs_violation_mask: PcieBitField = PcieBitField(bit_mask=(1 << 21), desc="ACS Violation Mask")
    uncorr_int_err_mask: PcieBitField = PcieBitField(
        bit_mask=(1 << 22), desc="Uncorrectable Internal Error Mask"
    )
    mc_blocked_tlp_mask: PcieBitField = PcieBitField(bit_mask=(1 << 23), desc="MC Blocked TLP Mask")
    atomicop_egress_blk_mask: PcieBitField = PcieBitField(
        bit_mask=(1 << 24), desc="AtomicOp Egress Blocked Mask"
    )
    tlp_prefix_blk_err_mask: PcieBitField = PcieBitField(
        bit_mask=(1 << 25), desc="TLP Prefix Blocked Error Mask"
    )
    poisoned_tlp_egress_blk_mask: PcieBitField = PcieBitField(
        bit_mask=(1 << 26), desc="Poisoned TLP Egress Blocked Mask"
    )


class UncorrErrSevReg(PcieRegister):
    """AER register for Uncorrectable Error Severity Register"""

    offset: int = 0x0C
    width: int = 32
    desc: str = "7.8.4.4 Uncorrectable Error Severity Register (Offset 0Ch)"
    dlnk_protocol_err_sev: PcieBitField = PcieBitField(
        bit_mask=(1 << 4), desc="Data Link Protocol Error Severity"
    )
    surprise_dn_err_sev: PcieBitField = PcieBitField(
        bit_mask=(1 << 5), desc="Surprise Down Error Severity"
    )
    poisoned_tlp_rcvd_sev: PcieBitField = PcieBitField(
        bit_mask=(1 << 12), desc="Poisoned TLP Received Severity"
    )
    fc_proto_err_sev: PcieBitField = PcieBitField(
        bit_mask=(1 << 13), desc="Flow Control Protocol Error Severity"
    )
    cpl_timeout_sev: PcieBitField = PcieBitField(
        bit_mask=(1 << 14), desc="Completion Timeout Error Severity"
    )
    ca_sev: PcieBitField = PcieBitField(bit_mask=(1 << 15), desc="Completer Abort Error Severity")
    unexp_cpl_sev: PcieBitField = PcieBitField(
        bit_mask=(1 << 16), desc="Unexpected Completion Error Severity"
    )
    rx_overflow_sev: PcieBitField = PcieBitField(
        bit_mask=(1 << 17), desc="Receiver Overflow Severity"
    )
    malformed_tlp_sev: PcieBitField = PcieBitField(
        bit_mask=(1 << 18), desc="Malformed TLP Severity"
    )
    ecrc_err_sev: PcieBitField = PcieBitField(bit_mask=(1 << 19), desc="ECRC Error Severity")
    ur_err_sev: PcieBitField = PcieBitField(
        bit_mask=(1 << 20), desc="Unsupported Request Error Severity"
    )
    acs_violation_sev: PcieBitField = PcieBitField(
        bit_mask=(1 << 21), desc="ACS Violation Severity"
    )
    uncorr_int_err_sev: PcieBitField = PcieBitField(
        bit_mask=(1 << 22), desc="Uncorrectable Internal Error Severity"
    )
    mc_blocked_tlp_sev: PcieBitField = PcieBitField(
        bit_mask=(1 << 23), desc="MC Blocked TLP Severity"
    )
    atomicop_egress_blk_sev: PcieBitField = PcieBitField(
        bit_mask=(1 << 24), desc="AtomicOp Egress Blocked Severity"
    )
    tlp_prefix_blk_err_sev: PcieBitField = PcieBitField(
        bit_mask=(1 << 25), desc="TLP Prefix Blocked Error Severity"
    )
    poisoned_tlp_egress_blk_sev: PcieBitField = PcieBitField(
        bit_mask=(1 << 26), desc="Poisoned TLP Egress Blocked Severity"
    )


class CorrErrStatReg(PcieRegister):
    """AER register for Correctable Error Status Register"""

    offset: int = 0x10
    width: int = 32
    desc: str = "Correctable Error Status Register"
    rx_err_stat: PcieBitField = PcieBitField(bit_mask=(1 << 0), desc="Receiver Error Status")
    bad_tlp_stat: PcieBitField = PcieBitField(bit_mask=(1 << 6), desc="Bad TLP Status")
    bad_dllp_stat: PcieBitField = PcieBitField(bit_mask=(1 << 7), desc="Bad DLLP Status")
    replay_num_rollover_stat: PcieBitField = PcieBitField(
        bit_mask=(1 << 8), desc="REPLAY_NUM Rollover Status"
    )
    replay_timer_timeout_stat: PcieBitField = PcieBitField(
        bit_mask=(1 << 12), desc="Replay Timer Timeout Status"
    )
    advisory_non_fatal_err_stat: PcieBitField = PcieBitField(
        bit_mask=(1 << 13), desc="Advisory Non-Fatal Error Status"
    )
    corrected_int_err_stat: PcieBitField = PcieBitField(
        bit_mask=(1 << 14), desc="Corrected Internal Error Status"
    )
    hdr_log_overflow_stat: PcieBitField = PcieBitField(
        bit_mask=(1 << 15), desc="Header Log Overflow Status"
    )


class CorrErrMaskReg(PcieRegister):
    """AER register for Correctable Error Mask Register"""

    offset: int = 0x14
    width: int = 32
    desc: str = "7.8.4.6 Correctable Error Mask Register (Offset 14h)"
    rx_err_mask: PcieBitField = PcieBitField(bit_mask=(1 << 0), desc="Receiver Error Mask")
    bad_tlp_mask: PcieBitField = PcieBitField(bit_mask=(1 << 6), desc="Bad TLP Mask")
    bad_dllp_mask: PcieBitField = PcieBitField(bit_mask=(1 << 7), desc="Bad DLLP Mask")
    replay_num_rollover_mask: PcieBitField = PcieBitField(
        bit_mask=(1 << 8), desc="REPLAY_NUM Rollover Mask"
    )
    replay_timer_timeout_mask: PcieBitField = PcieBitField(
        bit_mask=(1 << 12), desc="Replay Timer Timeout Mask"
    )
    advisory_non_fatal_err_mask: PcieBitField = PcieBitField(
        bit_mask=(1 << 13), desc="Advisory Non-Fatal Error Mask"
    )
    corrected_int_err_mask: PcieBitField = PcieBitField(
        bit_mask=(1 << 14), desc="Corrected Internal Error Mask"
    )
    hdr_log_overflow_mask: PcieBitField = PcieBitField(
        bit_mask=(1 << 15), desc="Header Log Overflow Mask"
    )


class AerCapCtrlReg(PcieRegister):
    """AER register for Advanced Error Capabilities and Control Register"""

    offset: int = 0x18
    width: int = 32
    desc: str = "7.8.4.7 Advanced Error Capabilities and Control Register (Offset 18h)"
    fst_err_ptr: PcieBitField = PcieBitField(bit_mask=(0x1F), desc="First Error Pointer")
    ecrc_gen_cap: PcieBitField = PcieBitField(bit_mask=(1 << 5), desc="ECRC Generation Capable")
    ecrc_gen_en: PcieBitField = PcieBitField(bit_mask=(1 << 6), desc="ECRC Generation Enable")
    ecrc_chk_cap: PcieBitField = PcieBitField(bit_mask=(1 << 7), desc="ECRC Check Capable")
    ecrc_chk_en: PcieBitField = PcieBitField(bit_mask=(1 << 8), desc="ECRC Check Enable")
    multi_hdr_rec_cap: PcieBitField = PcieBitField(
        bit_mask=(1 << 9), desc="Multiple Header Recording Capable"
    )
    multi_hdr_rec_en: PcieBitField = PcieBitField(
        bit_mask=(1 << 10), desc="Multiple Header Recording Enable"
    )
    tlp_prefix_log_prsnt: PcieBitField = PcieBitField(
        bit_mask=(1 << 11), desc="TLP Prefix Log Present"
    )
    cpl_timeout_prefix_hdr_log_cap: PcieBitField = PcieBitField(
        bit_mask=(1 << 12), desc="Completion Timeout Prefix/Header Log Capable"
    )


class RootErrCmdReg(PcieRegister):
    """AER register for Root Error Command Register"""

    offset: int = 0x2C
    width: int = 32
    desc: str = "7.8.4.9 Root Error Command Register (Offset 2Ch)"
    corr_err_report_en: PcieBitField = PcieBitField(
        bit_mask=(1 << 0), desc="Correctable Error Reporting Enable"
    )
    non_fatal_err_report_en: PcieBitField = PcieBitField(
        bit_mask=(1 << 1), desc="Non-Fatal Error Reporting Enable"
    )
    fatal_err_report_en: PcieBitField = PcieBitField(
        bit_mask=(1 << 2), desc="Fatal Error Reporting Enable"
    )


class RootErrStatReg(PcieRegister):
    """AER register for Root Error Status Register"""

    offset: int = 0x30
    width: int = 32
    desc: str = "Root Error Status Register"
    err_cor_rcvd: PcieBitField = PcieBitField(bit_mask=(1 << 0), desc="ERR_COR Received")
    multi_err_cor_rcvd: PcieBitField = PcieBitField(
        bit_mask=(1 << 1), desc="Multiple ERR_COR Received"
    )
    err_fatal_nonfatal_rcvd: PcieBitField = PcieBitField(
        bit_mask=(1 << 2), desc="ERR_FATAL/NONFATAL Received"
    )
    multi_err_fatal_nonfatal_rcvd: PcieBitField = PcieBitField(
        bit_mask=(1 << 3), desc="Multiple ERR_FATAL/NONFATAL Received"
    )
    fst_uncorr_fatal: PcieBitField = PcieBitField(
        bit_mask=(1 << 4), desc="First Uncorrectable Fatal"
    )
    non_fatal_err_msg_rcvd: PcieBitField = PcieBitField(
        bit_mask=(1 << 5), desc="Non-Fatal Error Messages Received"
    )
    fatal_err_msg_rcvd: PcieBitField = PcieBitField(
        bit_mask=(1 << 6), desc="Fatal Error Messages Received"
    )
    err_cor_subclass: PcieBitField = PcieBitField(bit_mask=(0x3 << 7), desc="ERR_COR Subclass")
    adv_err_int_msg_num: PcieBitField = PcieBitField(
        bit_mask=(0x1F << 27), desc="Advanced Error Interrupt Message Number"
    )


class ErrSrcIdReg(PcieRegister):
    """AER register for Error Source Identification Register"""

    offset: int = 0x34
    width: int = 32
    desc: str = "7.8.4.11 Error Source Identification Register (Offset 34h)"
    err_cor_src_id: PcieBitField = PcieBitField(
        bit_mask=0x0000FFFF, desc="ERR_COR Source Identification"
    )
    err_fatal_nonfatal_src_id: PcieBitField = PcieBitField(
        bit_mask=0xFFFF0000, desc="ERR_FATAL/NONFATAL Source Identification"
    )


class ECapAer(PcieCapStructure):
    """Extended Capability for Advanced Error Reporting"""

    extended: Optional[bool] = True
    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.AER
    offset: int = 0x00
    desc: str = "7.8.4 Advanced Error Reporting Extended Capability"
    aer_ecap: AerEcapHdr = AerEcapHdr()
    uncorr_err_stat: UncorrErrStatReg = UncorrErrStatReg()
    uncorr_err_mask: UncorrErrMaskReg = UncorrErrMaskReg()
    uncorr_err_sev: UncorrErrSevReg = UncorrErrSevReg()
    corr_err_stat: CorrErrStatReg = CorrErrStatReg()
    corr_err_mask: CorrErrMaskReg = CorrErrMaskReg()
    aer_cap_ctrl: AerCapCtrlReg = AerCapCtrlReg()
    root_err_cmd: RootErrCmdReg = RootErrCmdReg()
    root_err_stat: RootErrStatReg = RootErrStatReg()
    err_src_id: ErrSrcIdReg = ErrSrcIdReg()


class ECapVc(PcieCapStructure):
    """Extended Capability for Virtual Channel"""

    extended: Optional[bool] = True
    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.VCEC
    offset: int = 0x00
    desc: str = "7.9.1 Virtual Channel Extended Capability"


class ECapDsn(PcieCapStructure):
    """Extended Capability for Device Serial Number"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.DSN
    offset: int = 0x00
    desc: str = "7.9.3 Device Serial Number Extended Capability"


class ECapPb(PcieCapStructure):
    """Extended Capability for Power Budgeting"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.PWR_BUDGET
    offset: int = 0x00
    desc: str = "7.8.1 Power Budgeting Extended Capability"


class ECapRclink(PcieCapStructure):
    """Extended Capability for Root Complex Link Declaration"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.LNK_DCLR
    offset: int = 0x00
    desc: str = "7.9.8.1 Root Complex Link Declaration Extended Capability Header (Offset 00h)"


class ECapRcilink(PcieCapStructure):
    """Extended Capability for Root Complex Internal Link Control"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.LNK_CEC
    offset: int = 0x00
    desc: str = "7.9.9 Root Complex Internal Link Control Extended Capability"


class ECapRcecoll(PcieCapStructure):
    """Extended Capability for Root Complex Event Collector Endpoint Association"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.RCECOLL
    offset: int = 0x00
    desc: str = (
        "7.9.10 Root Complex Event Collector Endpoint Association Extended Capability (Dell)"
    )


class ECapMfvc(PcieCapStructure):
    """Extended Capability for Multi-Function Virtual Channel"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.MFVC
    offset: int = 0x00
    desc: str = "7.9.2 Multi-Function Virtual Channel Extended Capability"


class ECapVc2(PcieCapStructure):
    """Extended Capability for Virtual Channel 2"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.VC2
    offset: int = 0x00
    desc: str = "7.9.1 Virtual Channel Extended Capability"


class ECapRcrb(PcieCapStructure):
    """Extended Capability for RCRB Header"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.RCRB
    offset: int = 0x00
    desc: str = "7.9.7 RCRB Header Extended Capability"


class ECapVndr(PcieCapStructure):
    """Extended Capability for Vendor-Specific"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.VNDR
    offset: int = 0x00
    desc: str = "7.9.5 Vendor-Specific Extended Capability"


class ECapCac(PcieCapStructure):
    """Extended Capability for Configuration Access Correlation"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.CAC
    offset: int = 0x00
    desc: str = "7.7. Configuration Access Correlation Extended Capability"


class ECapAcs(PcieCapStructure):
    """Extended Capability for ACS"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.ACS
    offset: int = 0x00
    desc: str = "7.7.8 ACS Extended Capability"


class ECapAri(PcieCapStructure):
    """Extended Capability for ARI"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.ARI
    offset: int = 0x00
    desc: str = "7.8.7 ARI Extended Capability"


class ECapAts(PcieCapStructure):
    """Extended Capability for ATS"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.ATS
    offset: int = 0x00
    desc: str = "10.5.1 ATS Extended Capability"


class ECapSriov(PcieCapStructure):
    """Extended Capability for SR-IOV"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.SRIOV
    offset: int = 0x00
    desc: str = "9.3.3 SR-IOV Extended Capability"


class ECapMriov(PcieCapStructure):
    """Extended Capability for MR-IOV"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.MRIOV
    offset: int = 0x00
    desc: str = "MR-IOV Extended Capability (MR-IOV)"


class ECapMcast(PcieCapStructure):
    """Extended Capability for Multicast"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.MULTCAST
    offset: int = 0x00
    desc: str = "7.9.11 Multicast Extended Capability"


class ECapPri(PcieCapStructure):
    """Extended Capability for Page Request Interface"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.PAGE_REQ
    offset: int = 0x00
    desc: str = "10.5.2 Page Request Extended Capability Structure"


class ECapAMD(PcieCapStructure):
    """Extended Capability for AMD"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.AMD
    offset: int = 0x00
    desc: str = "Reserved for AMD"


class ECapReba(PcieCapStructure):
    """Extended Capability for Resizable BAR"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.RBAR
    offset: int = 0x00
    desc: str = "7.8.6 Resizable BAR Extended Capability"


class ECapDpa(PcieCapStructure):
    """Extended Capability for Dynamic Power Allocation"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.DPA
    offset: int = 0x00
    desc: str = "7.9.12 Dynamic Power Allocation Extended Capability (DPA Capability)"


class ECapTph(PcieCapStructure):
    """Extended Capability for TPH"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.TPH
    offset: int = 0x00
    desc: str = "7.9.13.1 TPH Requester Extended Capability Header (Offset 00h)"


class ECapLtr(PcieCapStructure):
    """Extended Capability for LTR"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.LTR
    offset: int = 0x00
    desc: str = "7.8.2 Latency Tolerance Reporting (LTR) Extended Capability"


class LaneErrorStatReg(PcieRegister):
    """Lane error status register"""

    desc: str = "Lane Error Status Register"
    offset: int = 0x08
    width: int = 32
    lane0_err_stat: PcieBitField = PcieBitField(
        bit_mask=0xFFFFFFFF,
        desc="Lane Error Status Bits - Each bit indicates if the corresponding Lane detected a Lane-based error.",
    )


class ECapSecpci(PcieCapStructure):
    """Extended Capability for Secondary PCI Express"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.SPCI
    offset: int = 0x00
    desc: str = "7.7.3 Secondary PCI Express Extended Capability"
    lane_err_stat: LaneErrorStatReg = LaneErrorStatReg()


class ECapPmux(PcieCapStructure):
    """Extended Capability for PMUX"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.PMUX
    offset: int = 0x00
    desc: str = "G.5 PMUX Extended Capability"


class ECapPasid(PcieCapStructure):
    """Extended Capability for PASID"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.PASID
    offset: int = 0x00
    desc: str = "7.8.8 PASID Extended Capability Structure"


class ECapLnr(PcieCapStructure):
    """Extended Capability for LN Requester"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.LN
    offset: int = 0x00
    desc: str = "7.9.14 LN Requester Extended Capability (LNR Capability)"


class ECapDpc(PcieCapStructure):
    """Extended Capability for DPC"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.DPC
    offset: int = 0x00
    desc: str = "7.9.15 DPC Extended Capability"


class ECapL1pm(PcieCapStructure):
    """Extended Capability for L1 PM Substates"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.L1PM
    offset: int = 0x00
    desc: str = "7.8.3 L1 PM Substates Extended Capability"


class ECapPtm(PcieCapStructure):
    """Extended Capability for PTM"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.PTM
    offset: int = 0x00
    desc: str = "7.9.16 Precision Time Management Extended Capability (PTM Capability)"


class ECapMpcie(PcieCapStructure):
    """Extended Capability for M-PCIe"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.MPCIE
    offset: int = 0x00
    desc: str = "PCI Express over M-PHY Extended Capability (M-PCIe)"


class ECapFrs(PcieCapStructure):
    """Extended Capability for FRS Queueing"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.FRS
    offset: int = 0x00
    desc: str = "7.8.9 FRS Queueing Extended Capability"


class ECapRtr(PcieCapStructure):
    """Extended Capability for Readiness Time Reporting"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.RTR
    offset: int = 0x00
    desc: str = "7.9.17 Readiness Time Reporting Extended Capability"


class ECapDvsec(PcieCapStructure):
    """Extended Capability for Designated Vendor-Specific"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.DVENDR
    offset: int = 0x00
    desc: str = "7.9.6 Designated Vendor-Specific Extended Capability (DVSEC)"


class ECapVfRebar(PcieCapStructure):
    """Extended Capability for VF Resizable BAR"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.VFBAR
    offset: int = 0x00
    desc: str = "9.3.7.5 VF Resizable BAR Extended Capability"


class ECapDlnk(PcieCapStructure):
    """Extended Capability for Downstream Link"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.DLF
    offset: int = 0x00
    desc: str = "7.7.4 Data Link Feature Extended Capability"


class Phy16GtEcapHdr(PcieRegister):
    """Extended Capability for 16.0 GT/s Physical Layer"""

    offset: int = 0x00
    width: int = 32
    desc: str = "7.7.5.1 Physical Layer 16.0 GT/s Extended Capability Header (Offset 00h)"
    pcie_ecap_id: PcieBitField = PcieBitField(
        bit_mask=0x0000FFFF, desc="PCI Express Extended Capability ID"
    )
    cap_ver: PcieBitField = PcieBitField(bit_mask=0x000F0000, desc="Capability Version")
    nxt_cap_offset: PcieBitField = PcieBitField(bit_mask=0xFFF00000, desc="Next Capability Offset")


class Phy16GtEcapStat(PcieRegister):
    """Register for 16.0 GT/s Physical Layer Status"""

    offset: int = 0x0C
    width: int = 32
    desc: str = "16.0 GT/s Status Register"
    eq_16gt_cpl: PcieBitField = PcieBitField(
        bit_mask=(1 << 0), desc="Equalization 16.0 GT/s Complete"
    )
    eq_16gt_ph1_success: PcieBitField = PcieBitField(
        bit_mask=(1 << 1), desc="Equalization 16.0 GT/s Phase 1 Successful"
    )
    eq_16gt_ph2_success: PcieBitField = PcieBitField(
        bit_mask=(1 << 2), desc="Equalization 16.0 GT/s Phase 2 Successful"
    )
    eq_16gt_ph3_success: PcieBitField = PcieBitField(
        bit_mask=(1 << 3), desc="Equalization 16.0 GT/s Phase 3 Successful"
    )
    lnk_eq_req_16gt: PcieBitField = PcieBitField(
        bit_mask=(1 << 4), desc="Link Equalization Request 16.0 GT/s"
    )


class ParityMisMatchStat16GT(PcieRegister):
    """Register for 16.0 GT/s Parity Mismatch Status"""

    pos: int = 10
    width: int = 32
    offset: int = 0x10
    desc: str = "16.0 GT/s Local Data Parity Mismatch Status Register"


class RetimerFstPartiyRetimerMismatchStat16gt(PcieRegister):
    """Rgister for 16.0 GT/s First Retimer Data Parity Mismatch Status"""

    pos: int = 14
    width: int = 32
    offset: int = 0x14
    desc: str = "16.0 GT/s First Retimer Data Parity Mismatch Status Register"


class RetimerSecPartiyRetimerMismatchStat16gt(PcieRegister):
    """Register for 16.0 GT/s Second Retimer Data Parity Mismatch Status"""

    pos: int = 18
    width: int = 32
    offset: int = 0x18
    desc: str = "16.0 GT/s Second Retimer Data Parity Mismatch Status Register"


class EqCtl16Gt0(PcieRegister):
    """Register for 16.0 GT/s Equalization Control 0"""

    offset: int
    width: int = 8
    desc: str = "7.7.5.9 16.0 GT/s Lane Equalization Control Register (Offsets 20h to 3Ch)"
    upstream_eq_ctl_16gt_0: PcieBitField = PcieBitField(
        bit_mask=0x000000FF, desc="Upstream Equalization Control 16.0 GT/s 0"
    )
    downstream_eq_ctl_16gt_0: PcieBitField = PcieBitField(
        bit_mask=0x0000FF00, desc="Downstream Equalization Control 16.0 GT/s 0"
    )


class ECap16Gt(PcieCapStructure):
    """Extended Capability for 16.0 GT/s Physical Layer"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.PL_16GT
    offset: int = 0x00
    desc: str = "7.7.5 Physical Layer 16.0 GT/s Extended Capability"
    header: Phy16GtEcapHdr = Phy16GtEcapHdr()
    status: Phy16GtEcapStat = Phy16GtEcapStat()
    parity_mismatch_stat: ParityMisMatchStat16GT = ParityMisMatchStat16GT()
    retimer_fst_parity_mismatch_stat: RetimerFstPartiyRetimerMismatchStat16gt = (
        RetimerFstPartiyRetimerMismatchStat16gt()
    )
    retimer_sec_parity_mismatch_stat: RetimerSecPartiyRetimerMismatchStat16gt = (
        RetimerSecPartiyRetimerMismatchStat16gt()
    )
    eq_ctl_16gt_0: EqCtl16Gt0 = EqCtl16Gt0(offset=0x20, desc="16GT/s Equalization Control 0")
    eq_ctl_16gt_1: EqCtl16Gt0 = EqCtl16Gt0(offset=0x21, desc="16GT/s Equalization Control 1")
    eq_ctl_16gt_2: EqCtl16Gt0 = EqCtl16Gt0(offset=0x22, desc="16GT/s Equalization Control 2")
    eq_ctl_16gt_3: EqCtl16Gt0 = EqCtl16Gt0(offset=0x23, desc="16GT/s Equalization Control 3")
    eq_ctl_16gt_4: EqCtl16Gt0 = EqCtl16Gt0(offset=0x24, desc="16GT/s Equalization Control 4")
    eq_ctl_16gt_5: EqCtl16Gt0 = EqCtl16Gt0(offset=0x25, desc="16GT/s Equalization Control 5")
    eq_ctl_16gt_6: EqCtl16Gt0 = EqCtl16Gt0(offset=0x26, desc="16GT/s Equalization Control 6")
    eq_ctl_16gt_7: EqCtl16Gt0 = EqCtl16Gt0(offset=0x27, desc="16GT/s Equalization Control 7")
    eq_ctl_16gt_8: EqCtl16Gt0 = EqCtl16Gt0(offset=0x28, desc="16GT/s Equalization Control 8")
    eq_ctl_16gt_9: EqCtl16Gt0 = EqCtl16Gt0(offset=0x29, desc="16GT/s Equalization Control 9")
    eq_ctl_16gt_10: EqCtl16Gt0 = EqCtl16Gt0(offset=0x2A, desc="16GT/s Equalization Control 10")
    eq_ctl_16gt_11: EqCtl16Gt0 = EqCtl16Gt0(offset=0x2B, desc="16GT/s Equalization Control 11")
    eq_ctl_16gt_12: EqCtl16Gt0 = EqCtl16Gt0(offset=0x2C, desc="16GT/s Equalization Control 12")
    eq_ctl_16gt_13: EqCtl16Gt0 = EqCtl16Gt0(offset=0x2D, desc="16GT/s Equalization Control 13")
    eq_ctl_16gt_14: EqCtl16Gt0 = EqCtl16Gt0(offset=0x2E, desc="16GT/s Equalization Control 14")
    eq_ctl_16gt_15: EqCtl16Gt0 = EqCtl16Gt0(offset=0x2F, desc="16GT/s Equalization Control 15")
    eq_ctl_16gt_16: EqCtl16Gt0 = EqCtl16Gt0(offset=0x30, desc="16GT/s Equalization Control 16")
    eq_ctl_16gt_17: EqCtl16Gt0 = EqCtl16Gt0(offset=0x31, desc="16GT/s Equalization Control 17")
    eq_ctl_16gt_18: EqCtl16Gt0 = EqCtl16Gt0(offset=0x32, desc="16GT/s Equalization Control 18")
    eq_ctl_16gt_19: EqCtl16Gt0 = EqCtl16Gt0(offset=0x33, desc="16GT/s Equalization Control 19")
    eq_ctl_16gt_20: EqCtl16Gt0 = EqCtl16Gt0(offset=0x34, desc="16GT/s Equalization Control 20")
    eq_ctl_16gt_21: EqCtl16Gt0 = EqCtl16Gt0(offset=0x35, desc="16GT/s Equalization Control 21")
    eq_ctl_16gt_22: EqCtl16Gt0 = EqCtl16Gt0(offset=0x36, desc="16GT/s Equalization Control 22")
    eq_ctl_16gt_23: EqCtl16Gt0 = EqCtl16Gt0(offset=0x37, desc="16GT/s Equalization Control 23")
    eq_ctl_16gt_24: EqCtl16Gt0 = EqCtl16Gt0(offset=0x38, desc="16GT/s Equalization Control 24")
    eq_ctl_16gt_25: EqCtl16Gt0 = EqCtl16Gt0(offset=0x39, desc="16GT/s Equalization Control 25")
    eq_ctl_16gt_26: EqCtl16Gt0 = EqCtl16Gt0(offset=0x3A, desc="16GT/s Equalization Control 26")
    eq_ctl_16gt_27: EqCtl16Gt0 = EqCtl16Gt0(offset=0x3B, desc="16GT/s Equalization Control 27")
    eq_ctl_16gt_28: EqCtl16Gt0 = EqCtl16Gt0(offset=0x3C, desc="16GT/s Equalization Control 28")
    eq_ctl_16gt_29: EqCtl16Gt0 = EqCtl16Gt0(offset=0x3D, desc="16GT/s Equalization Control 29")
    eq_ctl_16gt_30: EqCtl16Gt0 = EqCtl16Gt0(offset=0x3E, desc="16GT/s Equalization Control 30")
    eq_ctl_16gt_31: EqCtl16Gt0 = EqCtl16Gt0(offset=0x3F, desc="16GT/s Equalization Control 31")


class ECapLmr(PcieCapStructure):
    """Extended Capability for Lane Margining at the Receiver"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.LM
    offset: int = 0x00
    desc: str = "7.7.7 Lane Margining at the Receiver Extended Capability"


class ECapHierId(PcieCapStructure):
    """Extended Capability for Hierarchy ID"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.HID
    offset: int = 0x00
    desc: str = "7.9.18 Hierarchy ID Extended Capability"


class ECapNpem(PcieCapStructure):
    """Extended Capability for Native PCIe Enclosure Management"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.NPEM
    offset: int = 0x00
    desc: str = (
        "7.9.20 Native PCIe Enclosure Management Extended Capability (NPEM Extended Capability)"
    )


class Phy32GtEcapHdr(PcieRegister):
    """Extended Capability for 32.0 GT/s Physical Layer"""

    offset: int = 0x00
    width: int = 32
    desc: str = "7.7.6.1 Physical Layer 32.0 GT/s Extended Capability Header (Offset 00h)"
    pcie_ecap_id: PcieBitField = PcieBitField(
        bit_mask=0x0000FFFF, desc="PCI Express Extended Capability ID"
    )
    cap_ver: PcieBitField = PcieBitField(bit_mask=0x000F0000, desc="Capability Version")
    nxt_cap_offset: PcieBitField = PcieBitField(bit_mask=0xFFF00000, desc="Next Capability Offset")


class Phy32GtEcapCapReg(PcieRegister):
    """Register for 32.0 GT/s Capabilities"""

    offset: int = 0x04
    width: int = 32
    desc: str = "7.7.6.2 32.0 GT/s Capabilities Register (Offset 04h"
    eq_bypass_hi_rate: PcieBitField = PcieBitField(
        bit_mask=(1 << 0), desc="Equalization bypass to highest rate Supported"
    )
    no_equi_needed: PcieBitField = PcieBitField(
        bit_mask=(1 << 1), desc="No Equalization Needed Supported - When Set"
    )
    modified_ts_usage_mode_0_supported: PcieBitField = PcieBitField(
        bit_mask=(1 << 8), desc="Modified TS Usage Mode 0 Supported"
    )
    modified_ts_usage_mode_1_supported: PcieBitField = PcieBitField(
        bit_mask=(1 << 9), desc="Modified TS Usage Mode 1 Supported"
    )
    modified_ts_usage_mode_2_supported: PcieBitField = PcieBitField(
        bit_mask=(1 << 10), desc="Modified TS Usage Mode 2 Supported"
    )
    modified_ts_reserved_usage_modes: PcieBitField = PcieBitField(
        bit_mask=(0x1F << 11), desc="Modified TS Reserved Usage Modes"
    )


class Phy32GtStatReg(PcieRegister):
    """Register for 32.0 GT/s Status"""

    offset: int = 0x0C
    width: int = 32
    desc: str = "32.0 GT/s Status Register"
    eq_32gt_cpl: PcieBitField = PcieBitField(
        bit_mask=(1 << 0), desc="Equalization 32.0 GT/s Complete"
    )
    eq_32gt_ph1_success: PcieBitField = PcieBitField(
        bit_mask=(1 << 1), desc="Equalization 32.0 GT/s Phase 1 Successful"
    )
    eq_32gt_ph2_success: PcieBitField = PcieBitField(
        bit_mask=(1 << 2), desc="Equalization 32.0 GT/s Phase 2 Successful"
    )
    eq_32gt_ph3_success: PcieBitField = PcieBitField(
        bit_mask=(1 << 3), desc="Equalization 32.0 GT/s Phase 3 Successful"
    )
    lnk_eq_req_32gt: PcieBitField = PcieBitField(
        bit_mask=(1 << 4), desc="Link Equalization Request 32.0 GT/s"
    )
    modified_ts_rcvd: PcieBitField = PcieBitField(bit_mask=(1 << 5), desc="Modified TS Received")
    rcvd_enhanced_link_behav_ctrl: PcieBitField = PcieBitField(
        bit_mask=(0x3 << 6), desc="Received Enhanced Link Behavior Control"
    )
    tx_precoding_on: PcieBitField = PcieBitField(bit_mask=(1 << 8), desc="Transmitter Precoding On")
    tx_precoding_req: PcieBitField = PcieBitField(
        bit_mask=(1 << 9), desc="Transmitter Precode Request"
    )
    no_eq_needed_rcvd: PcieBitField = PcieBitField(
        bit_mask=(1 << 10), desc="No Equalization Needed Received"
    )


class TransReceived32GTData1(PcieRegister):
    """Register for 32.0 GT/s Received Modified TS Data 1"""

    offset: int = 0x10
    width: int = 32
    desc: str = "7.7.6.5 Received Modified TS Data 1 Register (Offset 10h)"
    rcvd_mod_ts_usage_mode: PcieBitField = PcieBitField(
        bit_mask=(0x7 << 0), desc="Received Modified TS Usage Mode"
    )
    rcvd_mod_ts_info_1: PcieBitField = PcieBitField(
        bit_mask=(0xFFF << 3), desc="Received Modified TS Information 1"
    )
    rcvd_mod_ts_vendor_id: PcieBitField = PcieBitField(
        bit_mask=(0xFFFF << 16), desc="Received Modified TS Vendor ID"
    )


# 23:0 Received Modified TS Information 2
# 25:24 Alternate Protocol Negotiation Status
class TransReceived32GTData2(PcieRegister):
    """Register for 32.0 GT/s Received Modified TS Data 2"""

    offset: int = 0x14
    width: int = 32
    desc: str = "7.7.6.6 Received Modified TS Data 2 Register (Offset 14h)"
    rcvd_mod_ts_info_2: PcieBitField = PcieBitField(
        bit_mask=(0x7FF << 0), desc="Received Modified TS Information 2"
    )
    alt_proto_neg_status: PcieBitField = PcieBitField(
        bit_mask=(0x3 << 24), desc="Alternate Protocol Negotiation Status"
    )


class EqCtl32Gt0(PcieRegister):
    """Equalization Control for 32.0 GT/s"""

    offset: int
    width: int = 8
    desc: str = "7.7.6.9 32.0 GT/s Lane Equalization Control Register (Offset 20h to 3Ch)"
    upstream_eq_ctl_32gt_0: PcieBitField = PcieBitField(
        bit_mask=0x000000FF, desc="Upstream Equalization Control 32.0 GT/s 0"
    )
    downstream_eq_ctl_32gt_0: PcieBitField = PcieBitField(
        bit_mask=0x0000FF00, desc="Downstream Equalization Control 32.0 GT/s 0"
    )


class ECap32Gts(PcieCapStructure):
    """Extended Capability for 32.0 GT/s Physical Layer"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.PL_32GT
    offset: int = 0x00
    desc: str = "7.7.6 Physical Layer 32.0 GT/s Extended Capability"
    header: Phy32GtEcapHdr = Phy32GtEcapHdr()
    cap_reg: Phy32GtEcapCapReg = Phy32GtEcapCapReg()
    status: Phy32GtStatReg = Phy32GtStatReg()
    recv_data_1: TransReceived32GTData1 = TransReceived32GTData1()
    recv_data_2: TransReceived32GTData2 = TransReceived32GTData2()
    trans_data_1: TransReceived32GTData1 = TransReceived32GTData1(offset=0x18)
    trans_data_2: TransReceived32GTData2 = TransReceived32GTData2(offset=0x1C)
    eq_ctl_32gt_0: EqCtl32Gt0 = EqCtl32Gt0(offset=0x20, desc="32GT/s Equalization Control 0")
    eq_ctl_32gt_1: EqCtl32Gt0 = EqCtl32Gt0(offset=0x21, desc="32GT/s Equalization Control 1")
    eq_ctl_32gt_2: EqCtl32Gt0 = EqCtl32Gt0(offset=0x22, desc="32GT/s Equalization Control 2")
    eq_ctl_32gt_3: EqCtl32Gt0 = EqCtl32Gt0(offset=0x23, desc="32GT/s Equalization Control 3")
    eq_ctl_32gt_4: EqCtl32Gt0 = EqCtl32Gt0(offset=0x24, desc="32GT/s Equalization Control 4")
    eq_ctl_32gt_5: EqCtl32Gt0 = EqCtl32Gt0(offset=0x25, desc="32GT/s Equalization Control 5")
    eq_ctl_32gt_6: EqCtl32Gt0 = EqCtl32Gt0(offset=0x26, desc="32GT/s Equalization Control 6")
    eq_ctl_32gt_7: EqCtl32Gt0 = EqCtl32Gt0(offset=0x27, desc="32GT/s Equalization Control 7")
    eq_ctl_32gt_8: EqCtl32Gt0 = EqCtl32Gt0(offset=0x28, desc="32GT/s Equalization Control 8")
    eq_ctl_32gt_9: EqCtl32Gt0 = EqCtl32Gt0(offset=0x29, desc="32GT/s Equalization Control 9")
    eq_ctl_32gt_10: EqCtl32Gt0 = EqCtl32Gt0(offset=0x2A, desc="32GT/s Equalization Control 10")
    eq_ctl_32gt_11: EqCtl32Gt0 = EqCtl32Gt0(offset=0x2B, desc="32GT/s Equalization Control 11")
    eq_ctl_32gt_12: EqCtl32Gt0 = EqCtl32Gt0(offset=0x2C, desc="32GT/s Equalization Control 12")
    eq_ctl_32gt_13: EqCtl32Gt0 = EqCtl32Gt0(offset=0x2D, desc="32GT/s Equalization Control 13")
    eq_ctl_32gt_14: EqCtl32Gt0 = EqCtl32Gt0(offset=0x2E, desc="32GT/s Equalization Control 14")
    eq_ctl_32gt_15: EqCtl32Gt0 = EqCtl32Gt0(offset=0x2F, desc="32GT/s Equalization Control 15")
    eq_ctl_32gt_32: EqCtl32Gt0 = EqCtl32Gt0(offset=0x30, desc="32GT/s Equalization Control 32")
    eq_ctl_32gt_17: EqCtl32Gt0 = EqCtl32Gt0(offset=0x31, desc="32GT/s Equalization Control 17")
    eq_ctl_32gt_18: EqCtl32Gt0 = EqCtl32Gt0(offset=0x32, desc="32GT/s Equalization Control 18")
    eq_ctl_32gt_19: EqCtl32Gt0 = EqCtl32Gt0(offset=0x33, desc="32GT/s Equalization Control 19")
    eq_ctl_32gt_20: EqCtl32Gt0 = EqCtl32Gt0(offset=0x34, desc="32GT/s Equalization Control 20")
    eq_ctl_32gt_21: EqCtl32Gt0 = EqCtl32Gt0(offset=0x35, desc="32GT/s Equalization Control 21")
    eq_ctl_32gt_22: EqCtl32Gt0 = EqCtl32Gt0(offset=0x36, desc="32GT/s Equalization Control 22")
    eq_ctl_32gt_23: EqCtl32Gt0 = EqCtl32Gt0(offset=0x37, desc="32GT/s Equalization Control 23")
    eq_ctl_32gt_24: EqCtl32Gt0 = EqCtl32Gt0(offset=0x38, desc="32GT/s Equalization Control 24")
    eq_ctl_32gt_25: EqCtl32Gt0 = EqCtl32Gt0(offset=0x39, desc="32GT/s Equalization Control 25")
    eq_ctl_32gt_26: EqCtl32Gt0 = EqCtl32Gt0(offset=0x3A, desc="32GT/s Equalization Control 26")
    eq_ctl_32gt_27: EqCtl32Gt0 = EqCtl32Gt0(offset=0x3B, desc="32GT/s Equalization Control 27")
    eq_ctl_32gt_28: EqCtl32Gt0 = EqCtl32Gt0(offset=0x3C, desc="32GT/s Equalization Control 28")
    eq_ctl_32gt_29: EqCtl32Gt0 = EqCtl32Gt0(offset=0x3D, desc="32GT/s Equalization Control 29")
    eq_ctl_32gt_30: EqCtl32Gt0 = EqCtl32Gt0(offset=0x3E, desc="32GT/s Equalization Control 30")
    eq_ctl_32gt_31: EqCtl32Gt0 = EqCtl32Gt0(offset=0x3F, desc="32GT/s Equalization Control 31")


class ECapAltProtocol(PcieCapStructure):
    """Extended Capability for Alternate Protocol"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.ALT_PROTOCOL
    offset: int = 0x00
    desc: str = "7.9.21 Alternate Protocol Extended Capability"


class ECapSfi(PcieCapStructure):
    """Extended Capability for System Firmware Intermediary"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.SFI
    offset: int = 0x00
    desc: str = "7.9.23 System Firmware Intermediary (SFI) Extended Capability"


class ECapDoe(PcieCapStructure):
    """Extended Capability for DOE"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.DOE
    offset: int = 0x00
    desc: str = "Cap DOE"


class ECapIntegrityDoe(PcieCapStructure):
    """Extended Capability for Integrity DOE"""

    cap_id: ClassVar[Enum] = ExtendedCapabilityEnum.INT_DOE
    offset: int = 0x00
    desc: str = "Int Cap DOE"


class PcieCfgSpace(BaseModel):
    """Holds the base registers and capability structures of a PCIe device

    - type_0_configuration: Type 0 Configuration Space, this is both the shared registers and the type0 specific registers
    - type_1_configuration: Type 1 Configuration Space, this is both the shared registers and the type1 specific registers
    - capability_pointers: A dictionary of capability pointers to the offset of the capability structure
    - extended_capability_pointers: A dictionary of extended capability pointers to the offset of the extended capability structure
    - cap_structure: A dictionary of capability structures
    - ecap_structure: A dictionary of extended capability structures

    """

    type_0_configuration: Type0Configuration = Type0Configuration()
    type_1_configuration: Type1Configuration = Type1Configuration()
    capability_pointers: Dict[CapabilityEnum, int] = {}
    extended_capability_pointers: Dict[ExtendedCapabilityEnum, int] = {}
    # SerializeAsAny is used to allow for the structure to be any of the capability structures so all registers and fields are dumped
    cap_structure: Dict[CapabilityEnum, SerializeAsAny[PcieCapStructure]] = {}
    ecap_structure: Dict[ExtendedCapabilityEnum, SerializeAsAny[PcieCapStructure]] = {}

    def get_struct(self, struct: type[AnyCap]) -> Optional[AnyCap]:
        """Get a structure from the cap_structure or ecap_structure based on the type

        Parameters
        ----------
        struct : type[AnyCap]
            The structure to get from the cap_structure or ecap_structure

        Returns
        -------
        Optional[AnyCap]
            The structure if it exists, otherwise None
        """
        if struct == Type0Configuration:
            return self.type_0_configuration  # type: ignore[return-value]
        if struct == Type1Configuration:
            return self.type_1_configuration  # type: ignore[return-value]

        if hasattr(struct, "cap_id"):
            cap = self.cap_structure.get(struct.cap_id, None)  # type: ignore[attr-defined]
            if cap:
                return cap  # type: ignore[return-value]
            ecap = self.ecap_structure.get(struct.cap_id, None)  # type: ignore[attr-defined]
            if ecap:
                return ecap  # type: ignore[return-value]
        return None

    @field_validator("extended_capability_pointers", mode="before")
    @classmethod
    def str_to_enum_extended(cls, dict_in: Dict[str, int]) -> Dict[Enum, int]:
        """Converts a dictionary with string keys to Enum keys

        Parameters
        ----------
        dict_in : Dict[str, int]
            The dictionary to convert

        Returns
        -------
        dict[Enum, int]
            The dictionary with Enum keys
        """
        dict_out: Dict[Enum, int] = {}
        for k, v in dict_in.items():
            if isinstance(k, str):
                dict_out[ExtendedCapabilityEnum(int(k))] = v
        return dict_out

    @field_validator("capability_pointers", mode="before")
    @classmethod
    def str_to_enum(cls, dict_in: Dict[str, int]) -> Dict[Enum, int]:
        """Converts a dictionary with string keys to Enum keys

        Parameters
        ----------
        dict_in : Dict[str, int]
            The dictionary to convert

        Returns
        -------
        dict[Enum, int]
            The dictionary with Enum keys
        """
        dict_out: Dict[Enum, int] = {}
        for k, v in dict_in.items():
            if isinstance(k, str):
                dict_out[CapabilityEnum(int(k))] = v
            else:
                dict_out[k] = v
        return dict_out

    @field_validator("cap_structure", mode="before")
    @classmethod
    def validate_cap_structure(
        cls, cap_in: Dict[Union[int, str, CapabilityEnum], SerializeAsAny[PcieCapStructure]]
    ) -> Dict[CapabilityEnum, PcieCapStructure]:
        """This adjust's a generic PcieCapStructure dict into a specific PcieCapStructure and therefore populating all registers and fields"""
        return cls.conform_json_dict_to_cap_struct(cap_in, CapabilityEnum)  # type: ignore[arg-type, return-value]

    @field_validator("ecap_structure", mode="before")
    @classmethod
    def validate_ecap_structure(
        cls,
        ecap_in: Dict[Union[int, str, ExtendedCapabilityEnum], SerializeAsAny[PcieCapStructure]],
    ) -> Dict[ExtendedCapabilityEnum, PcieCapStructure]:
        """This adjust's a generic PcieCapStructure dict into a specific PcieCapStructure and therefore populating all registers and fields"""
        return cls.conform_json_dict_to_cap_struct(ecap_in, ExtendedCapabilityEnum)  # type: ignore[arg-type, return-value]

    @classmethod
    def conform_json_dict_to_cap_struct(
        cls,
        cap_structure_in: Dict[Union[str, int, Enum], PcieCapStructure],
        enum_type: type[Enum],
    ) -> Dict[Enum, PcieCapStructure]:
        """This is needed for when the model is loaded from a json/dict. Since the type of PcieCapStructure
        does not fully describe which cap structure it is and which registers it has, pydantic just assumes
        it is the base class. To override this behaviour the cap_id is used to discover which structure it
        really should be. This is only done if the value of the validated attribute is a dict

        Parameters
        ----------
        cap_structure_in : Dict[Union[str, int, Enum], PcieCapStructure]
            A capability structure to fix from json input
        enum_type : type[Enum]
            Which enum to use for values

        Returns
        -------
        dict[Enum, PcieCapStructure]
            A dict where the values are now the fully defined structure instead of the base class
        """
        cap_out: Dict[Enum, PcieCapStructure] = {}
        for k, v in cap_structure_in.items():
            if isinstance(v, dict):
                if isinstance(k, str):
                    enum = enum_type(int(k))
                elif isinstance(k, enum_type):
                    enum = k
                cls = cap_id_to_class(enum)
                cap_out[enum] = cls(**v)
            else:
                cap_out[k] = v  # type: ignore[index]
        return cap_out


class PcieDataModel(DataModel):
    """class for collection of PCIe data.

    Optionals are used to allow for the data to be missing,
    This makes the data class more flexible for the analyzer
    which consumes only the required data. If any more data is
    required for the analyzer then they should not be set to
    default.

    - pcie_cfg_space: A dictionary of PCIe cfg space for the GPUs obtained with setpci command
    - lspci_verbose: Verbose collection of PCIe data
    - lspci_verbose_tree: Tree view of PCIe data
    - lspci_path: Path view of PCIe data for the GPUs
    - lspci_hex: Hex view of PCIe data for the GPUs

    """

    pcie_cfg_space: Dict[BdfStr, PcieCfgSpace]
    vf_pcie_cfg_space: Optional[Dict[BdfStr, PcieCfgSpace]] = None
