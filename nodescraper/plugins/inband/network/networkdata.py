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


class PensandoNicCard(BaseModel):
    """Pensando NIC card information from nicctl show card"""

    id: str  # Card ID (UUID format)
    pcie_bdf: str  # PCIe Bus:Device.Function (e.g., "0000:06:00.0")
    asic: Optional[str] = None  # ASIC type (e.g., "salina")
    fw_partition: Optional[str] = None  # Firmware partition (e.g., "A")
    serial_number: Optional[str] = None  # Serial number (e.g., "FPL25330294")


class PensandoNicDcqcn(BaseModel):
    """Pensando NIC DCQCN information from nicctl show dcqcn"""

    nic_id: str  # NIC ID (UUID format)
    pcie_bdf: str  # PCIe Bus:Device.Function (e.g., "0000:06:00.0")
    lif_id: Optional[str] = None  # Lif ID (UUID format)
    roce_device: Optional[str] = None  # ROCE device name (e.g., "rocep9s0")
    dcqcn_profile_id: Optional[str] = None  # DCQCN profile id (e.g., "1")
    status: Optional[str] = None  # Status (e.g., "Disabled")


class PensandoNicEnvironment(BaseModel):
    """Pensando NIC environment information from nicctl show environment"""

    nic_id: str  # NIC ID (UUID format)
    pcie_bdf: str  # PCIe Bus:Device.Function (e.g., "0000:06:00.0")
    # Power measurements in Watts
    total_power_drawn: Optional[float] = None  # Total power drawn (pin)
    core_power: Optional[float] = None  # Core power (pout1)
    arm_power: Optional[float] = None  # ARM power (pout2)
    # Temperature measurements in Celsius
    local_board_temperature: Optional[float] = None  # Local board temperature
    die_temperature: Optional[float] = None  # Die temperature
    # Voltage measurements in millivolts
    input_voltage: Optional[float] = None  # Input voltage
    core_voltage: Optional[float] = None  # Core voltage
    # Frequency measurements in MHz
    core_frequency: Optional[float] = None  # Core frequency
    cpu_frequency: Optional[float] = None  # CPU frequency
    p4_stage_frequency: Optional[float] = None  # P4 stage frequency


class PensandoNicPcieAts(BaseModel):
    """Pensando NIC PCIe ATS information from nicctl show pcie ats"""

    nic_id: str  # NIC ID (UUID format)
    pcie_bdf: str  # PCIe Bus:Device.Function (e.g., "0000:06:00.0")
    status: str  # Status (e.g., "Disabled", "Enabled")


class PensandoNicPort(BaseModel):
    """Pensando NIC port information from nicctl show port"""

    nic_id: str  # NIC ID (UUID format)
    pcie_bdf: str  # PCIe Bus:Device.Function (e.g., "0000:06:00.0")
    port_id: str  # Port ID (UUID format)
    port_name: str  # Port name (e.g., "eth1/1")
    # Spec fields
    spec_ifindex: Optional[str] = None
    spec_type: Optional[str] = None
    spec_speed: Optional[str] = None
    spec_admin_state: Optional[str] = None
    spec_fec_type: Optional[str] = None
    spec_pause_type: Optional[str] = None
    spec_num_lanes: Optional[int] = None
    spec_mtu: Optional[int] = None
    spec_tx_pause: Optional[str] = None
    spec_rx_pause: Optional[str] = None
    spec_auto_negotiation: Optional[str] = None
    # Status fields
    status_physical_port: Optional[int] = None
    status_operational_status: Optional[str] = None
    status_link_fsm_state: Optional[str] = None
    status_fec_type: Optional[str] = None
    status_cable_type: Optional[str] = None
    status_num_lanes: Optional[int] = None
    status_speed: Optional[str] = None
    status_auto_negotiation: Optional[str] = None
    status_mac_id: Optional[int] = None
    status_mac_channel: Optional[int] = None
    status_mac_address: Optional[str] = None
    status_transceiver_type: Optional[str] = None
    status_transceiver_state: Optional[str] = None
    status_transceiver_pid: Optional[str] = None


class PensandoNicQosScheduling(BaseModel):
    """QoS Scheduling entry"""

    priority: int
    scheduling_type: Optional[str] = None  # e.g., "DWRR"
    bandwidth: Optional[int] = None  # Bandwidth in percentage
    rate_limit: Optional[str] = None  # Rate limit (e.g., "N/A" or value in Gbps)


class PensandoNicQos(BaseModel):
    """Pensando NIC QoS information from nicctl show qos"""

    nic_id: str  # NIC ID (UUID format)
    pcie_bdf: str  # PCIe Bus:Device.Function (e.g., "0000:06:00.0")
    port_id: str  # Port ID (UUID format)
    classification_type: Optional[str] = None  # e.g., "DSCP"
    dscp_bitmap: Optional[str] = None  # DSCP bitmap
    dscp_range: Optional[str] = None  # DSCP range (e.g., "0-63")
    dscp_priority: Optional[int] = None  # Priority mapped from DSCP
    pfc_priority_bitmap: Optional[str] = None  # PFC priority bitmap
    pfc_no_drop_priorities: Optional[str] = None  # PFC no-drop priorities
    scheduling: List[PensandoNicQosScheduling] = Field(default_factory=list)  # Scheduling entries


class PensandoNicRdmaStatistic(BaseModel):
    """RDMA statistic entry"""

    name: str  # Statistic name
    count: int  # Count value


class PensandoNicRdmaStatistics(BaseModel):
    """Pensando NIC RDMA statistics from nicctl show rdma statistics"""

    nic_id: str  # NIC ID (UUID format)
    pcie_bdf: str  # PCIe Bus:Device.Function (e.g., "0000:06:00.0")
    statistics: List[PensandoNicRdmaStatistic] = Field(default_factory=list)  # Statistics entries


class PensandoNicVersionHostSoftware(BaseModel):
    """Pensando NIC host software version from nicctl show version host-software"""

    nicctl: Optional[str] = None  # nicctl version
    ipc_driver: Optional[str] = None  # IPC driver version
    ionic_driver: Optional[str] = None  # ionic driver version


class PensandoNicVersionFirmware(BaseModel):
    """Pensando NIC firmware version from nicctl show version firmware"""

    nic_id: str  # NIC ID (UUID format)
    pcie_bdf: str  # PCIe Bus:Device.Function (e.g., "0000:06:00.0")
    cpld: Optional[str] = None  # CPLD version
    boot0: Optional[str] = None  # Boot0 version
    uboot_a: Optional[str] = None  # Uboot-A version
    firmware_a: Optional[str] = None  # Firmware-A version
    device_config_a: Optional[str] = None  # Device config-A version


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
    pensando_nic_cards: List[PensandoNicCard] = Field(default_factory=list)
    pensando_nic_dcqcn: List[PensandoNicDcqcn] = Field(default_factory=list)
    pensando_nic_environment: List[PensandoNicEnvironment] = Field(default_factory=list)
    pensando_nic_pcie_ats: List[PensandoNicPcieAts] = Field(default_factory=list)
    pensando_nic_ports: List[PensandoNicPort] = Field(default_factory=list)
    pensando_nic_qos: List[PensandoNicQos] = Field(default_factory=list)
    pensando_nic_rdma_statistics: List[PensandoNicRdmaStatistics] = Field(default_factory=list)
    pensando_nic_version_host_software: Optional[PensandoNicVersionHostSoftware] = None
    pensando_nic_version_firmware: List[PensandoNicVersionFirmware] = Field(default_factory=list)
