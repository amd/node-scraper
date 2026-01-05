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


class IpAddress(BaseModel):
    """Individual IP address on an interface"""

    address: str  # "192.168.1.100"
    prefix_len: Optional[int] = None  # 24
    scope: Optional[str] = None  # "global", "link", "host"
    family: Optional[str] = None  # "inet", "inet6"
    label: Optional[str] = None  # interface label/alias
    broadcast: Optional[str] = None  # broadcast address


class NetworkInterface(BaseModel):
    """Network interface information"""

    name: str  # "eth0", "lo", etc
    index: Optional[int] = None  # interface index
    state: Optional[str] = None  # "UP", "DOWN", "UNKNOWN"
    mtu: Optional[int] = None  # Maximum Transmission Unit
    qdisc: Optional[str] = None  # Queuing discipline
    mac_address: Optional[str] = None  # MAC/hardware address
    flags: List[str] = Field(default_factory=list)  # ["UP", "BROADCAST", "MULTICAST"]
    addresses: List[IpAddress] = Field(default_factory=list)  # IP addresses on this interface


class Route(BaseModel):
    """Routing table entry"""

    destination: str  # "default", "192.168.1.0/24", etc
    gateway: Optional[str] = None  # Gateway IP
    device: Optional[str] = None  # Network interface
    protocol: Optional[str] = None  # "kernel", "boot", "static", etc
    scope: Optional[str] = None  # "link", "global", "host"
    metric: Optional[int] = None  # Route metric/priority
    source: Optional[str] = None  # Preferred source address
    table: Optional[str] = None  # Routing table name/number


class RoutingRule(BaseModel):
    """Routing policy rule"""

    priority: int  # Rule priority
    source: Optional[str] = None  # Source address/network
    destination: Optional[str] = None  # Destination address/network
    table: Optional[str] = None  # Routing table to use
    action: Optional[str] = None  # "lookup", "unreachable", "prohibit", etc
    iif: Optional[str] = None  # Input interface
    oif: Optional[str] = None  # Output interface
    fwmark: Optional[str] = None  # Firewall mark


class Neighbor(BaseModel):
    """ARP/Neighbor table entry"""

    ip_address: str  # IP address of the neighbor
    device: Optional[str] = None  # Network interface
    mac_address: Optional[str] = None  # Link layer (MAC) address
    state: Optional[str] = None  # "REACHABLE", "STALE", "DELAY", "PROBE", "FAILED", "INCOMPLETE"
    flags: List[str] = Field(default_factory=list)  # Additional flags like "router", "proxy"


class EthtoolInfo(BaseModel):
    """Ethtool information for a network interface"""

    interface: str  # Interface name this info belongs to
    raw_output: str  # Raw ethtool command output
    settings: Dict[str, str] = Field(default_factory=dict)  # Parsed key-value settings
    supported_link_modes: List[str] = Field(default_factory=list)  # Supported link modes
    advertised_link_modes: List[str] = Field(default_factory=list)  # Advertised link modes
    speed: Optional[str] = None  # Link speed (e.g., "10000Mb/s")
    duplex: Optional[str] = None  # Duplex mode (e.g., "Full")
    port: Optional[str] = None  # Port type (e.g., "Twisted Pair")
    auto_negotiation: Optional[str] = None  # Auto-negotiation status (e.g., "on", "off")
    link_detected: Optional[str] = None  # Link detection status (e.g., "yes", "no")


class BroadcomNicDevice(BaseModel):
    """Broadcom NIC device information from niccli --list_devices"""

    device_num: int  # Device number (1, 2, 3, etc.)
    model: Optional[str] = None  # e.g., "Broadcom BCM57608 1x400G QSFP-DD PCIe Ethernet NIC"
    adapter_port: Optional[str] = None  # e.g., "Adp#1 Port#1"
    interface_name: Optional[str] = None  # e.g., "benic1p1"
    mac_address: Optional[str] = None  # e.g., "8C:84:74:37:C3:70"
    pci_address: Optional[str] = None  # e.g., "0000:06:00.0"


class BroadcomNicQosAppEntry(BaseModel):
    """APP TLV entry in Broadcom NIC QoS configuration"""

    priority: Optional[int] = None
    sel: Optional[int] = None
    dscp: Optional[int] = None
    protocol: Optional[str] = None  # "UDP or DCCP", etc.
    port: Optional[int] = None


class BroadcomNicQos(BaseModel):
    """Broadcom NIC QoS information from niccli --dev X qos --ets --show"""

    device_num: int  # Device number this QoS info belongs to
    raw_output: str  # Raw command output
    # ETS Configuration
    prio_map: Dict[int, int] = Field(
        default_factory=dict
    )  # Priority to TC mapping {0: 0, 1: 0, ...}
    tc_bandwidth: List[int] = Field(
        default_factory=list
    )  # TC bandwidth percentages [50, 50, 0, ...]
    tsa_map: Dict[int, str] = Field(
        default_factory=dict
    )  # TC to TSA mapping {0: "ets", 1: "ets", ...}
    # PFC Configuration
    pfc_enabled: Optional[int] = None  # Bitmap of PFC enabled priorities
    # APP TLV entries
    app_entries: List[BroadcomNicQosAppEntry] = Field(default_factory=list)
    # TC Rate Limit
    tc_rate_limit: List[int] = Field(default_factory=list)  # TC rate limits [100, 100, 100, ...]


class NetworkDataModel(DataModel):
    """Complete network configuration data"""

    interfaces: List[NetworkInterface] = Field(default_factory=list)
    routes: List[Route] = Field(default_factory=list)
    rules: List[RoutingRule] = Field(default_factory=list)
    neighbors: List[Neighbor] = Field(default_factory=list)
    ethtool_info: Dict[str, EthtoolInfo] = Field(
        default_factory=dict
    )  # Interface name -> EthtoolInfo mapping
    broadcom_nic_devices: List[BroadcomNicDevice] = Field(default_factory=list)
    broadcom_nic_qos: Dict[int, BroadcomNicQos] = Field(
        default_factory=dict
    )  # Device number -> QoS info mapping
