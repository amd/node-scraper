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
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from nodescraper.models import DataModel


class IbstatDevice(BaseModel):
    """InfiniBand device information from ibstat"""

    ca_name: Optional[str] = None  # CA name (e.g., "mlx5_0")
    ca_type: Optional[str] = None  # CA type
    number_of_ports: Optional[int] = None  # Number of physical ports
    firmware_version: Optional[str] = None  # Firmware version
    hardware_version: Optional[str] = None  # Hardware version
    node_guid: Optional[str] = None  # Node GUID
    system_image_guid: Optional[str] = None  # System image GUID
    ports: Dict[int, Dict[str, str]] = Field(default_factory=dict)  # Port number -> port attributes
    raw_output: str = ""  # Raw command output


class IbvDeviceInfo(BaseModel):
    """InfiniBand verbs device information from ibv_devinfo"""

    device: Optional[str] = None  # Device name (e.g., "mlx5_0")
    node_guid: Optional[str] = None  # Node GUID
    sys_image_guid: Optional[str] = None  # System image GUID
    vendor_id: Optional[str] = None  # Vendor ID
    vendor_part_id: Optional[str] = None  # Vendor part ID
    hw_ver: Optional[str] = None  # Hardware version
    fw_ver: Optional[str] = None  # Firmware version
    node_type: Optional[str] = None  # Node type
    transport_type: Optional[str] = None  # Transport type (e.g., "InfiniBand", "Ethernet")
    ports: Dict[int, Dict[str, str]] = Field(default_factory=dict)  # Port number -> port attributes
    raw_output: str = ""  # Raw command output


class IbdevNetdevMapping(BaseModel):
    """Mapping between IB device and network interface"""

    ib_device: str  # InfiniBand device name (e.g., "mlx5_0")
    port: int  # Port number
    netdev: Optional[str] = None  # Network device name (e.g., "ib0", "eth0")
    state: Optional[str] = None  # Port state (e.g., "Up", "Down")
    pkey: Optional[str] = None  # Partition key
    guid: Optional[str] = None  # GUID


class OfedInfo(BaseModel):
    """OFED version and information"""

    version: Optional[str] = None  # OFED version
    raw_output: str = ""  # Raw command output


class MstDevice(BaseModel):
    """Mellanox Software Tools device information"""

    device: str  # Device path (e.g., "/dev/mst/mt4123_pciconf0")
    pci_address: Optional[str] = None  # PCI address
    rdma_device: Optional[str] = None  # RDMA device name
    net_device: Optional[str] = None  # Network device name
    attributes: Dict[str, str] = Field(default_factory=dict)  # Additional attributes


class MstStatus(BaseModel):
    """Mellanox Software Tools status"""

    mst_started: bool = False  # Whether MST service is started
    devices: List[MstDevice] = Field(default_factory=list)  # List of MST devices
    raw_output: str = ""  # Raw command output


class RdmaDevice(BaseModel):
    """RDMA device information from rdma command"""

    device: str  # Device name (e.g., "mlx5_0")
    node_type: Optional[str] = None  # Node type
    transport: Optional[str] = None  # Transport type
    node_guid: Optional[str] = None  # Node GUID
    sys_image_guid: Optional[str] = None  # System image GUID
    state: Optional[str] = None  # Device state
    attributes: Dict[str, str] = Field(default_factory=dict)  # Additional attributes


class RdmaLink(BaseModel):
    """RDMA link information"""

    device: str  # Device name
    port: int  # Port number
    state: Optional[str] = None  # Link state
    physical_state: Optional[str] = None  # Physical state
    netdev: Optional[str] = None  # Associated network device
    attributes: Dict[str, str] = Field(default_factory=dict)  # Additional attributes


class RdmaInfo(BaseModel):
    """Complete RDMA information from rdma command"""

    devices: List[RdmaDevice] = Field(default_factory=list)  # RDMA devices
    links: List[RdmaLink] = Field(default_factory=list)  # RDMA links
    raw_output: str = ""  # Raw command output


class FabricsDataModel(DataModel):
    """Complete InfiniBand/RDMA fabrics configuration data"""

    ibstat_devices: List[IbstatDevice] = Field(default_factory=list)  # ibstat output
    ibv_devices: List[IbvDeviceInfo] = Field(default_factory=list)  # ibv_devinfo output
    ibdev_netdev_mappings: List[IbdevNetdevMapping] = Field(
        default_factory=list
    )  # ibdev2netdev output
    ofed_info: Optional[OfedInfo] = None  # OFED version info
    mst_status: Optional[MstStatus] = None  # MST status
    rdma_info: Optional[RdmaInfo] = None  # RDMA information
