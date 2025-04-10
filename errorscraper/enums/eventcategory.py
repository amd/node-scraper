from enum import auto, unique

from errorscraper.utils import AutoNameStrEnum


@unique
class EventCategory(AutoNameStrEnum):
    """Class defining shared event categories
    - SSH
        SSH-related errors, e.g. connection refused, timeout, etc.
    - RAS
        Any RAS events that are customer-visible, including from memory, IO, compute, platform, etc.
    - IO
        IO-related SoC or platform IO component, e.g. PCIe, XGMI, HUBs, DF, CXL, USB, USR, NICs
        Does not include IO errors which are customer-visible via RAS
    - OS
        Generic Operating System events.
        Does not include specific events from OS which point to another category
    - PLATFORM
        Generic Platform Errors e.g. topo enumeration
        Platform-specific errors which do not fall under other categories (e.g. BMC, SMC, UBB)
        Does not include specific platform events which point to another category
    - APPLICATION
        End user application errors/failures/outputs, e.g. internal tools give back non-zero return code
    - MEMORY
        Memory-related SoC or platform component, e.g. HBM, UMC, DRAM, SRAM, DDR, etc.
        Does not include anything customer-visible via RAS
    - STORAGE
        SSD/HDD/storage media hardware events, filesystem events
    - COMPUTE
        Events from any of the following AMD IP: GFX, CPU, SDMA, VCN
        Does not include anything customer-visible via RAS
    - FW
        FW Timeouts, internal FW problems, FW version mismatches
    - SW_DRIVER
        Generic SW errors/failures with amdgpu (e.g. dmesg error on driver load)
        Does not include specific events from driver which point to another category
    - BIOS
        SBIOS/VBIOS/IFWI Errors
    - INFRASTRUCTURE
        Network, IT issues, Downtime
    - RUNTIME
        Framework issues, does not include content failures
    - UNKNOWN
        This is not a catch-all. It is intended for errors which inherently cannot be categorized due to limitations on how they are collected/analyzed.
    """

    SSH = auto()
    RAS = auto()
    IO = auto()
    OS = auto()
    PLATFORM = auto()
    APPLICATION = auto()
    MEMORY = auto()
    STORAGE = auto()
    COMPUTE = auto()
    FW = auto()
    SW_DRIVER = auto()
    BIOS = auto()
    INFRASTRUCTURE = auto()
    RUNTIME = auto()
    UNKNOWN = auto()
