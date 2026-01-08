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
import re
from typing import Dict, List, Optional, Tuple

from nodescraper.base import InBandDataCollector
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.models import TaskResult

from .networkdata import (
    BroadcomNicDevice,
    BroadcomNicQos,
    BroadcomNicQosAppEntry,
    EthtoolInfo,
    IpAddress,
    Neighbor,
    NetworkDataModel,
    NetworkInterface,
    PensandoNicCard,
    PensandoNicDcqcn,
    PensandoNicEnvironment,
    PensandoNicPcieAts,
    PensandoNicPort,
    PensandoNicQos,
    PensandoNicQosScheduling,
    PensandoNicRdmaStatistic,
    PensandoNicRdmaStatistics,
    PensandoNicVersionFirmware,
    PensandoNicVersionHostSoftware,
    Route,
    RoutingRule,
)


class NetworkCollector(InBandDataCollector[NetworkDataModel, None]):
    """Collect network configuration details using ip command"""

    DATA_MODEL = NetworkDataModel
    CMD_ADDR = "ip addr show"
    CMD_ROUTE = "ip route show"
    CMD_RULE = "ip rule show"
    CMD_NEIGHBOR = "ip neighbor show"
    CMD_ETHTOOL_TEMPLATE = "ethtool {interface}"

    # LLDP commands
    CMD_LLDPCLI_NEIGHBOR = "lldpcli show neighbor"
    CMD_LLDPCTL = "lldpctl"

    # Broadcom NIC commands
    CMD_NICCLI_LISTDEV = "niccli --list_devices"
    CMD_NICCLI_GETQOS_TEMPLATE = "niccli --dev {device_num} qos --ets --show"

    # Pensando NIC commands
    CMD_NICCTL_COMMANDS = [
        "nicctl show card",
        "nicctl show dcqcn",
        "nicctl show environment",
        "nicctl show pcie ats",
        "nicctl show port",
        "nicctl show qos",
        "nicctl show rdma statistics",
        "nicctl show version host-software",
        "nicctl show version firmware",
    ]

    def _parse_ip_addr(self, output: str) -> List[NetworkInterface]:
        """Parse 'ip addr show' output into NetworkInterface objects.

        Args:
            output: Raw output from 'ip addr show' command

        Returns:
            List of NetworkInterface objects
        """
        interfaces = {}
        current_interface = None

        for line in output.splitlines():
            # Check if this is an interface header line
            # Format: 1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN ...
            if re.match(r"^\d+:", line):
                parts = line.split()

                # Extract interface index and name
                idx_str = parts[0].rstrip(":")
                try:
                    index = int(idx_str)
                except ValueError:
                    index = None

                ifname = parts[1].rstrip(":")
                current_interface = ifname

                # Extract flags
                flags: List[str] = []
                if "<" in line:
                    flag_match = re.search(r"<([^>]+)>", line)
                    if flag_match:
                        flags = flag_match.group(1).split(",")

                # Extract other attributes
                mtu = None
                qdisc = None
                state = None

                # Known keyword-value pairs
                keyword_value_pairs = ["mtu", "qdisc", "state"]

                for i, part in enumerate(parts):
                    if part in keyword_value_pairs and i + 1 < len(parts):
                        if part == "mtu":
                            try:
                                mtu = int(parts[i + 1])
                            except ValueError:
                                pass
                        elif part == "qdisc":
                            qdisc = parts[i + 1]
                        elif part == "state":
                            state = parts[i + 1]

                interfaces[ifname] = NetworkInterface(
                    name=ifname,
                    index=index,
                    state=state,
                    mtu=mtu,
                    qdisc=qdisc,
                    flags=flags,
                )

            # Check if this is a link line (contains MAC address)
            # Format:     link/ether 00:40:a6:96:d7:5a brd ff:ff:ff:ff:ff:ff
            elif "link/" in line and current_interface:
                parts = line.split()
                if "link/ether" in parts:
                    idx = parts.index("link/ether")
                    if idx + 1 < len(parts):
                        interfaces[current_interface].mac_address = parts[idx + 1]
                elif "link/loopback" in parts:
                    # Loopback interface
                    if len(parts) > 1:
                        interfaces[current_interface].mac_address = parts[1]

            # Check if this is an inet/inet6 address line
            # Format:     inet 10.228.152.67/22 brd 10.228.155.255 scope global noprefixroute enp129s0
            elif any(x in line for x in ["inet ", "inet6 "]) and current_interface:
                parts = line.split()

                # Parse the IP address
                family = None
                address = None
                prefix_len = None
                scope = None
                broadcast = None

                for i, part in enumerate(parts):
                    if part in ["inet", "inet6"]:
                        family = part
                        if i + 1 < len(parts):
                            addr_part = parts[i + 1]
                            if "/" in addr_part:
                                address, prefix = addr_part.split("/")
                                try:
                                    prefix_len = int(prefix)
                                except ValueError:
                                    pass
                            else:
                                address = addr_part
                    elif part == "scope" and i + 1 < len(parts):
                        scope = parts[i + 1]
                    elif part in ["brd", "broadcast"] and i + 1 < len(parts):
                        broadcast = parts[i + 1]

                if address and current_interface in interfaces:
                    ip_addr = IpAddress(
                        address=address,
                        prefix_len=prefix_len,
                        family=family,
                        scope=scope,
                        broadcast=broadcast,
                        label=current_interface,
                    )
                    interfaces[current_interface].addresses.append(ip_addr)

        return list(interfaces.values())

    def _parse_ip_route(self, output: str) -> List[Route]:
        """Parse 'ip route show' output into Route objects.

        Args:
            output: Raw output from 'ip route show' command

        Returns:
            List of Route objects
        """
        routes = []

        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue

            parts = line.split()
            if not parts:
                continue

            # First part is destination (can be "default" or a network)
            destination = parts[0]

            route = Route(destination=destination)

            # Known keyword-value pairs
            keyword_value_pairs = ["via", "dev", "proto", "scope", "metric", "src", "table"]

            # Parse route attributes
            i = 1
            while i < len(parts):
                if parts[i] in keyword_value_pairs and i + 1 < len(parts):
                    keyword = parts[i]
                    value = parts[i + 1]

                    if keyword == "via":
                        route.gateway = value
                    elif keyword == "dev":
                        route.device = value
                    elif keyword == "proto":
                        route.protocol = value
                    elif keyword == "scope":
                        route.scope = value
                    elif keyword == "metric":
                        try:
                            route.metric = int(value)
                        except ValueError:
                            pass
                    elif keyword == "src":
                        route.source = value
                    elif keyword == "table":
                        route.table = value
                    i += 2
                else:
                    i += 1

            routes.append(route)

        return routes

    def _parse_ip_rule(self, output: str) -> List[RoutingRule]:
        """Parse 'ip rule show' output into RoutingRule objects.
           Example ip rule: 200: from 172.16.0.0/12 to 8.8.8.8 iif wlan0 oif eth0 fwmark 0x20 table vpn_table

        Args:
            output: Raw output from 'ip rule show' command

        Returns:
            List of RoutingRule objects
        """
        rules = []

        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue

            parts = line.split()
            if not parts:
                continue

            # First part is priority followed by ":"
            priority_str = parts[0].rstrip(":")
            try:
                priority = int(priority_str)
            except ValueError:
                continue

            rule = RoutingRule(priority=priority)

            # Parse rule attributes
            i = 1
            while i < len(parts):
                if parts[i] == "from" and i + 1 < len(parts):
                    if parts[i + 1] != "all":
                        rule.source = parts[i + 1]
                    i += 2
                elif parts[i] == "to" and i + 1 < len(parts):
                    if parts[i + 1] != "all":
                        rule.destination = parts[i + 1]
                    i += 2
                elif parts[i] in ["lookup", "table"] and i + 1 < len(parts):
                    rule.table = parts[i + 1]
                    if parts[i] == "lookup":
                        rule.action = "lookup"
                    i += 2
                elif parts[i] == "iif" and i + 1 < len(parts):
                    rule.iif = parts[i + 1]
                    i += 2
                elif parts[i] == "oif" and i + 1 < len(parts):
                    rule.oif = parts[i + 1]
                    i += 2
                elif parts[i] == "fwmark" and i + 1 < len(parts):
                    rule.fwmark = parts[i + 1]
                    i += 2
                elif parts[i] in ["unreachable", "prohibit", "blackhole"]:
                    rule.action = parts[i]
                    i += 1
                else:
                    i += 1

            rules.append(rule)

        return rules

    def _parse_ip_neighbor(self, output: str) -> List[Neighbor]:
        """Parse 'ip neighbor show' output into Neighbor objects.

        Args:
            output: Raw output from 'ip neighbor show' command

        Returns:
            List of Neighbor objects
        """
        neighbors = []

        # Known keyword-value pairs (keyword takes next element as value)
        keyword_value_pairs = ["dev", "lladdr", "nud", "vlan", "via"]

        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue

            parts = line.split()
            if not parts:
                continue

            # First part is the IP address
            ip_address = parts[0]

            neighbor = Neighbor(ip_address=ip_address)

            # Parse neighbor attributes
            i = 1
            while i < len(parts):
                current = parts[i]

                # Check for known keyword-value pairs
                if current in keyword_value_pairs and i + 1 < len(parts):
                    if current == "dev":
                        neighbor.device = parts[i + 1]
                    elif current == "lladdr":
                        neighbor.mac_address = parts[i + 1]
                    # Other keyword-value pairs can be added here as needed
                    i += 2

                # Check if it's a state (all uppercase, typically single word)
                elif current.isupper() and current.isalpha():
                    # States: REACHABLE, STALE, DELAY, PROBE, FAILED, INCOMPLETE, PERMANENT, NOARP
                    # Future states will also be captured
                    neighbor.state = current
                    i += 1

                # Check if it looks like a MAC address (contains colons)
                elif ":" in current and not current.startswith("http"):
                    # Already handled by lladdr, but in case it appears standalone
                    if not neighbor.mac_address:
                        neighbor.mac_address = current
                    i += 1

                # Check if it looks like an IP address (has dots or is IPv6)
                elif "." in current or ("::" in current):
                    # Skip IP addresses that might appear (already captured as first element)
                    i += 1

                # Anything else that's a simple lowercase word is likely a flag
                elif current.isalpha() and current.islower():
                    # Flags: router, proxy, extern_learn, offload, managed, etc.
                    # Captures both known and future flags
                    neighbor.flags.append(current)
                    i += 1

                else:
                    # Unknown format, skip it
                    i += 1

            neighbors.append(neighbor)

        return neighbors

    def _parse_ethtool(self, interface: str, output: str) -> EthtoolInfo:
        """Parse 'ethtool <interface>' output into EthtoolInfo object.

        Args:
            interface: Name of the network interface
            output: Raw output from 'ethtool <interface>' command

        Returns:
            EthtoolInfo object with parsed data
        """
        ethtool_info = EthtoolInfo(interface=interface, raw_output=output)

        # Parse line by line
        current_section = None
        for line in output.splitlines():
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Detect sections (lines ending with colon and no tab prefix)
            if line_stripped.endswith(":") and not line.startswith("\t"):
                current_section = line_stripped.rstrip(":")
                continue

            # Parse key-value pairs (lines with colon in the middle)
            if ":" in line_stripped:
                # Split on first colon
                parts = line_stripped.split(":", 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()

                    # Store in settings dict
                    ethtool_info.settings[key] = value

                    # Extract specific important fields
                    if key == "Speed":
                        ethtool_info.speed = value
                    elif key == "Duplex":
                        ethtool_info.duplex = value
                    elif key == "Port":
                        ethtool_info.port = value
                    elif key == "Auto-negotiation":
                        ethtool_info.auto_negotiation = value
                    elif key == "Link detected":
                        ethtool_info.link_detected = value

            # Parse supported/advertised link modes (typically indented list items)
            elif current_section in ["Supported link modes", "Advertised link modes"]:
                # These are typically list items, possibly with speeds like "10baseT/Half"
                if line.startswith("\t") or line.startswith(" "):
                    mode = line_stripped
                    if current_section == "Supported link modes":
                        ethtool_info.supported_link_modes.append(mode)
                    elif current_section == "Advertised link modes":
                        ethtool_info.advertised_link_modes.append(mode)

        return ethtool_info

    def _parse_niccli_listdev(self, output: str) -> List[BroadcomNicDevice]:
        """Parse 'niccli --list_devices' output into BroadcomNicDevice objects.

        Args:
            output: Raw output from 'niccli --list_devices' command

        Returns:
            List of BroadcomNicDevice objects
        """
        devices = []
        current_device = None

        for line in output.splitlines():
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Check if this is a device header line
            match = re.match(r"^(\d+)\s*\)\s*(.+?)(?:\s+\((.+?)\))?$", line_stripped)
            if match:
                device_num_str = match.group(1)
                model = match.group(2).strip() if match.group(2) else None
                adapter_port = match.group(3).strip() if match.group(3) else None

                try:
                    device_num = int(device_num_str)
                except ValueError:
                    continue

                current_device = BroadcomNicDevice(
                    device_num=device_num,
                    model=model,
                    adapter_port=adapter_port,
                )
                devices.append(current_device)

            # Check for Device Interface Name line
            elif "Device Interface Name" in line and current_device:
                parts = line_stripped.split(":")
                if len(parts) >= 2:
                    current_device.interface_name = parts[1].strip()

            # Check for MAC Address line
            elif "MAC Address" in line and current_device:
                parts = line_stripped.split(":")
                if len(parts) >= 2:
                    # MAC address has colons, so rejoin the parts after first split
                    mac = ":".join(parts[1:]).strip()
                    current_device.mac_address = mac

            # Check for PCI Address line
            elif "PCI Address" in line and current_device:
                parts = line_stripped.split(":")
                if len(parts) >= 2:
                    # PCI address also has colons, rejoin
                    pci = ":".join(parts[1:]).strip()
                    current_device.pci_address = pci

        return devices

    def _parse_nicctl_card(self, output: str) -> List[PensandoNicCard]:
        """Parse 'nicctl show card' output into PensandoNicCard objects.

        Args:
            output: Raw output from 'nicctl show card' command

        Returns:
            List of PensandoNicCard objects
        """
        cards = []

        # Skip header lines and separator lines
        in_data_section = False

        for line in output.splitlines():
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Skip header line (starts with "Id")
            if line_stripped.startswith("Id"):
                in_data_section = True
                continue

            # Skip separator lines (mostly dashes)
            if re.match(r"^-+$", line_stripped):
                continue

            # Parse data lines after header
            if in_data_section:
                # Split by whitespace
                parts = line_stripped.split()

                # Expected format: Id PCIe_BDF ASIC F/W_partition Serial_number
                if len(parts) >= 2:
                    card = PensandoNicCard(
                        id=parts[0],
                        pcie_bdf=parts[1],
                        asic=parts[2] if len(parts) > 2 else None,
                        fw_partition=parts[3] if len(parts) > 3 else None,
                        serial_number=parts[4] if len(parts) > 4 else None,
                    )
                    cards.append(card)

        return cards

    def _parse_nicctl_dcqcn(self, output: str) -> List[PensandoNicDcqcn]:
        """Parse 'nicctl show dcqcn' output into PensandoNicDcqcn objects.

        Args:
            output: Raw output from 'nicctl show dcqcn' command

        Returns:
            List of PensandoNicDcqcn objects
        """
        dcqcn_entries = []
        current_entry = None

        for line in output.splitlines():
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Check for NIC line
            if line_stripped.startswith("NIC :"):
                # Save previous entry if exists
                if current_entry:
                    dcqcn_entries.append(current_entry)

                # Parse NIC ID and PCIe BDF
                # Format: "NIC : <id> (<pcie_bdf>)"
                match = re.match(
                    r"NIC\s*:\s*([a-f0-9\-]+)\s*\(([0-9a-f:\.]+)\)", line_stripped, re.IGNORECASE
                )
                if match:
                    nic_id = match.group(1)
                    pcie_bdf = match.group(2)
                    current_entry = PensandoNicDcqcn(
                        nic_id=nic_id,
                        pcie_bdf=pcie_bdf,
                    )
                continue

            # Skip separator lines (dashes or asterisks)
            if re.match(r"^[-*]+$", line_stripped):
                continue

            # Parse fields within current entry
            if current_entry and ":" in line_stripped:
                parts = line_stripped.split(":", 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()

                    if key == "Lif id":
                        current_entry.lif_id = value
                    elif key == "ROCE device":
                        current_entry.roce_device = value
                    elif key == "DCQCN profile id":
                        current_entry.dcqcn_profile_id = value
                    elif key == "Status":
                        current_entry.status = value

        # Add the last entry if exists
        if current_entry:
            dcqcn_entries.append(current_entry)

        return dcqcn_entries

    def _parse_nicctl_environment(self, output: str) -> List[PensandoNicEnvironment]:
        """Parse 'nicctl show environment' output into PensandoNicEnvironment objects.

        Args:
            output: Raw output from 'nicctl show environment' command

        Returns:
            List of PensandoNicEnvironment objects
        """
        environment_entries = []
        current_entry = None

        for line in output.splitlines():
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Check for NIC line
            if line_stripped.startswith("NIC :"):
                # Save previous entry if exists
                if current_entry:
                    environment_entries.append(current_entry)

                # Parse NIC ID and PCIe BDF
                # Format: "NIC : <id> (<pcie_bdf>)"
                match = re.match(
                    r"NIC\s*:\s*([a-f0-9\-]+)\s*\(([0-9a-f:\.]+)\)", line_stripped, re.IGNORECASE
                )
                if match:
                    nic_id = match.group(1)
                    pcie_bdf = match.group(2)
                    current_entry = PensandoNicEnvironment(
                        nic_id=nic_id,
                        pcie_bdf=pcie_bdf,
                    )
                continue

            # Skip separator lines (dashes)
            if re.match(r"^-+$", line_stripped):
                continue

            # Skip section headers (Power(W):, Temperature(C):, etc.)
            if line_stripped.endswith("):"):
                continue

            # Parse fields within current entry
            if current_entry and ":" in line_stripped:
                parts = line_stripped.split(":", 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value_str = parts[1].strip()

                    # Try to parse the value as float
                    try:
                        value = float(value_str)
                    except ValueError:
                        continue

                    # Map keys to fields
                    if key == "Total power drawn (pin)" or key == "Total power drawn":
                        current_entry.total_power_drawn = value
                    elif key == "Core power (pout1)" or key == "Core power":
                        current_entry.core_power = value
                    elif key == "ARM power (pout2)" or key == "ARM power":
                        current_entry.arm_power = value
                    elif key == "Local board temperature":
                        current_entry.local_board_temperature = value
                    elif key == "Die temperature":
                        current_entry.die_temperature = value
                    elif key == "Input voltage":
                        current_entry.input_voltage = value
                    elif key == "Core voltage":
                        current_entry.core_voltage = value
                    elif key == "Core frequency":
                        current_entry.core_frequency = value
                    elif key == "CPU frequency":
                        current_entry.cpu_frequency = value
                    elif key == "P4 stage frequency":
                        current_entry.p4_stage_frequency = value

        # Add the last entry if exists
        if current_entry:
            environment_entries.append(current_entry)

        return environment_entries

    def _parse_nicctl_pcie_ats(self, output: str) -> List[PensandoNicPcieAts]:
        """Parse 'nicctl show pcie ats' output into PensandoNicPcieAts objects.

        Args:
            output: Raw output from 'nicctl show pcie ats' command

        Returns:
            List of PensandoNicPcieAts objects
        """
        pcie_ats_entries = []

        for line in output.splitlines():
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Parse line format: "NIC : <id> (<pcie_bdf>) : <status>"
            if line_stripped.startswith("NIC :"):
                match = re.match(
                    r"NIC\s*:\s*([a-f0-9\-]+)\s*\(([0-9a-f:\.]+)\)\s*:\s*(\w+)",
                    line_stripped,
                    re.IGNORECASE,
                )
                if match:
                    nic_id = match.group(1)
                    pcie_bdf = match.group(2)
                    status = match.group(3)
                    entry = PensandoNicPcieAts(
                        nic_id=nic_id,
                        pcie_bdf=pcie_bdf,
                        status=status,
                    )
                    pcie_ats_entries.append(entry)

        return pcie_ats_entries

    def _parse_nicctl_port(self, output: str) -> List[PensandoNicPort]:
        """Parse 'nicctl show port' output into PensandoNicPort objects.

        Args:
            output: Raw output from 'nicctl show port' command

        Returns:
            List of PensandoNicPort objects
        """
        port_entries = []
        current_entry = None
        current_section = None  # 'spec' or 'status'
        current_nic_id = None
        current_pcie_bdf = None

        for line in output.splitlines():
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Check for NIC line
            if line_stripped.startswith("NIC") and ":" in line_stripped:
                # Save previous entry if exists
                if current_entry:
                    port_entries.append(current_entry)
                    current_entry = None

                # Parse NIC ID and PCIe BDF
                match = re.match(
                    r"NIC\s*:\s*([a-f0-9\-]+)\s*\(([0-9a-f:\.]+)\)", line_stripped, re.IGNORECASE
                )
                if match:
                    current_nic_id = match.group(1)
                    current_pcie_bdf = match.group(2)
                continue

            # Check for Port line
            if (
                line_stripped.startswith("Port")
                and ":" in line_stripped
                and current_nic_id
                and current_pcie_bdf
            ):
                # Save previous entry if exists
                if current_entry:
                    port_entries.append(current_entry)

                # Parse Port ID and Port name
                match = re.match(
                    r"Port\s*:\s*([a-f0-9\-]+)\s*\(([^\)]+)\)", line_stripped, re.IGNORECASE
                )
                if match:
                    port_id = match.group(1)
                    port_name = match.group(2)
                    current_entry = PensandoNicPort(
                        nic_id=current_nic_id,
                        pcie_bdf=current_pcie_bdf,
                        port_id=port_id,
                        port_name=port_name,
                    )
                continue

            # Skip separator lines (dashes)
            if re.match(r"^-+$", line_stripped):
                continue

            # Check for section headers
            if line_stripped.endswith(":"):
                if line_stripped == "Spec:":
                    current_section = "spec"
                elif line_stripped == "Status:":
                    current_section = "status"
                continue

            # Parse fields within current entry and section
            if current_entry and current_section and ":" in line_stripped:
                parts = line_stripped.split(":", 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()

                    if current_section == "spec":
                        if key == "Ifindex":
                            current_entry.spec_ifindex = value
                        elif key == "Type":
                            current_entry.spec_type = value
                        elif key == "speed":
                            current_entry.spec_speed = value
                        elif key == "Admin state":
                            current_entry.spec_admin_state = value
                        elif key == "FEC type":
                            current_entry.spec_fec_type = value
                        elif key == "Pause type":
                            current_entry.spec_pause_type = value
                        elif key == "Number of lanes":
                            try:
                                current_entry.spec_num_lanes = int(value)
                            except ValueError:
                                pass
                        elif key == "MTU":
                            try:
                                current_entry.spec_mtu = int(value)
                            except ValueError:
                                pass
                        elif key == "TX pause":
                            current_entry.spec_tx_pause = value
                        elif key == "RX pause":
                            current_entry.spec_rx_pause = value
                        elif key == "Auto negotiation":
                            current_entry.spec_auto_negotiation = value
                    elif current_section == "status":
                        if key == "Physical port":
                            try:
                                current_entry.status_physical_port = int(value)
                            except ValueError:
                                pass
                        elif key == "Operational status":
                            current_entry.status_operational_status = value
                        elif key == "Link FSM state":
                            current_entry.status_link_fsm_state = value
                        elif key == "FEC type":
                            current_entry.status_fec_type = value
                        elif key == "Cable type":
                            current_entry.status_cable_type = value
                        elif key == "Number of lanes":
                            try:
                                current_entry.status_num_lanes = int(value)
                            except ValueError:
                                pass
                        elif key == "speed":
                            current_entry.status_speed = value
                        elif key == "Auto negotiation":
                            current_entry.status_auto_negotiation = value
                        elif key == "MAC ID":
                            try:
                                current_entry.status_mac_id = int(value)
                            except ValueError:
                                pass
                        elif key == "MAC channel":
                            try:
                                current_entry.status_mac_channel = int(value)
                            except ValueError:
                                pass
                        elif key == "MAC address":
                            current_entry.status_mac_address = value
                        elif key == "Transceiver type":
                            current_entry.status_transceiver_type = value
                        elif key == "Transceiver state":
                            current_entry.status_transceiver_state = value
                        elif key == "Transceiver PID":
                            current_entry.status_transceiver_pid = value

        # Add the last entry if exists
        if current_entry:
            port_entries.append(current_entry)

        return port_entries

    def _parse_nicctl_qos(self, output: str) -> List[PensandoNicQos]:
        """Parse 'nicctl show qos' output into PensandoNicQos objects.

        Args:
            output: Raw output from 'nicctl show qos' command

        Returns:
            List of PensandoNicQos objects
        """
        qos_entries = []
        current_entry = None
        current_nic_id = None
        current_pcie_bdf = None
        in_scheduling_table = False

        for line in output.splitlines():
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Check for NIC line: "NIC  : 42424650-4c32-3533-3330-323934000000 (0000:06:00.0)"
            if line_stripped.startswith("NIC") and ":" in line_stripped:
                # Save previous entry if exists
                if current_entry:
                    qos_entries.append(current_entry)
                    current_entry = None

                # Parse NIC ID and PCIe BDF
                match = re.match(
                    r"NIC\s*:\s*([a-f0-9\-]+)\s*\(([0-9a-f:\.]+)\)", line_stripped, re.IGNORECASE
                )
                if match:
                    current_nic_id = match.group(1)
                    current_pcie_bdf = match.group(2)
                in_scheduling_table = False
                continue

            # Check for Port line: "Port : 0490814a-6c40-4242-4242-000011010000"
            if (
                line_stripped.startswith("Port")
                and ":" in line_stripped
                and current_nic_id
                and current_pcie_bdf
            ):
                # Save previous entry if exists
                if current_entry:
                    qos_entries.append(current_entry)

                # Parse Port ID
                parts = line_stripped.split(":")
                if len(parts) >= 2:
                    port_id = parts[1].strip()
                    current_entry = PensandoNicQos(
                        nic_id=current_nic_id,
                        pcie_bdf=current_pcie_bdf,
                        port_id=port_id,
                    )
                in_scheduling_table = False
                continue

            # Skip separator lines (dashes) but don't reset scheduling table flag
            if re.match(r"^-+$", line_stripped):
                continue

            # Check for section headers
            if current_entry:
                # Classification type
                if "Classification type" in line:
                    parts = line_stripped.split(":")
                    if len(parts) >= 2:
                        current_entry.classification_type = parts[1].strip()

                # DSCP bitmap
                elif "DSCP bitmap" in line and "==>" in line:
                    parts = line_stripped.split("==>")
                    if len(parts) >= 2:
                        bitmap_part = parts[0].split(":")
                        if len(bitmap_part) >= 2:
                            current_entry.dscp_bitmap = bitmap_part[1].strip()
                        priority_part = parts[1].split(":")
                        if len(priority_part) >= 2:
                            try:
                                current_entry.dscp_priority = int(priority_part[1].strip())
                            except ValueError:
                                pass

                # DSCP range
                elif line_stripped.startswith("DSCP") and "==>" in line and "bitmap" not in line:
                    parts = line_stripped.split("==>")
                    if len(parts) >= 2:
                        dscp_part = parts[0].split(":")
                        if len(dscp_part) >= 2:
                            current_entry.dscp_range = dscp_part[1].strip()
                        priority_part = parts[1].split(":")
                        if len(priority_part) >= 2:
                            try:
                                current_entry.dscp_priority = int(priority_part[1].strip())
                            except ValueError:
                                pass

                # PFC priority bitmap
                elif "PFC priority bitmap" in line:
                    parts = line_stripped.split(":")
                    if len(parts) >= 2:
                        current_entry.pfc_priority_bitmap = parts[1].strip()

                # PFC no-drop priorities
                elif "PFC no-drop priorities" in line:
                    parts = line_stripped.split(":")
                    if len(parts) >= 2:
                        current_entry.pfc_no_drop_priorities = parts[1].strip()

                # Scheduling table header
                elif "Priority" in line and "Scheduling" in line:
                    in_scheduling_table = True
                    continue

                # Parse scheduling table entries
                elif in_scheduling_table and not line_stripped.startswith("---"):
                    # Try to parse scheduling entry
                    # Format: "0         DWRR        0         N/A"
                    parts = line_stripped.split()
                    if len(parts) >= 2:
                        try:
                            priority = int(parts[0])
                            scheduling_type = parts[1] if len(parts) > 1 else None
                            bandwidth = None
                            rate_limit = None
                            if len(parts) > 2:
                                try:
                                    bandwidth = int(parts[2])
                                except ValueError:
                                    pass
                            if len(parts) > 3:
                                rate_limit = parts[3]

                            sched_entry = PensandoNicQosScheduling(
                                priority=priority,
                                scheduling_type=scheduling_type,
                                bandwidth=bandwidth,
                                rate_limit=rate_limit,
                            )
                            current_entry.scheduling.append(sched_entry)
                        except (ValueError, IndexError):
                            pass

        # Add the last entry if exists
        if current_entry:
            qos_entries.append(current_entry)

        return qos_entries

    def _parse_nicctl_rdma_statistics(self, output: str) -> List[PensandoNicRdmaStatistics]:
        """Parse 'nicctl show rdma statistics' output into PensandoNicRdmaStatistics objects.

        Args:
            output: Raw output from 'nicctl show rdma statistics' command

        Returns:
            List of PensandoNicRdmaStatistics objects
        """
        rdma_stats_entries = []
        current_entry = None
        in_statistics_table = False

        for line in output.splitlines():
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Check for NIC line: "NIC : 42424650-4c32-3533-3330-323934000000 (0000:06:00.0)"
            if line_stripped.startswith("NIC") and ":" in line_stripped:
                # Save previous entry if exists
                if current_entry:
                    rdma_stats_entries.append(current_entry)

                # Parse NIC ID and PCIe BDF
                match = re.match(
                    r"NIC\s*:\s*([a-f0-9\-]+)\s*\(([0-9a-f:\.]+)\)", line_stripped, re.IGNORECASE
                )
                if match:
                    nic_id = match.group(1)
                    pcie_bdf = match.group(2)
                    current_entry = PensandoNicRdmaStatistics(
                        nic_id=nic_id,
                        pcie_bdf=pcie_bdf,
                    )
                in_statistics_table = False
                continue

            # Skip separator lines (dashes)
            if re.match(r"^-+$", line_stripped):
                continue

            # Check for table header
            if "Name" in line and "Count" in line:
                in_statistics_table = True
                continue

            # Parse statistics entries
            if current_entry and in_statistics_table:
                # The format is: "Queue pair create                       1"
                # We need to split from the right to get the count
                parts = line_stripped.rsplit(None, 1)  # Split from right, max 1 split
                if len(parts) == 2:
                    name = parts[0].strip()
                    count_str = parts[1].strip()
                    try:
                        count = int(count_str)
                        stat_entry = PensandoNicRdmaStatistic(
                            name=name,
                            count=count,
                        )
                        current_entry.statistics.append(stat_entry)
                    except ValueError:
                        pass

        # Add the last entry if exists
        if current_entry:
            rdma_stats_entries.append(current_entry)

        return rdma_stats_entries

    def _parse_nicctl_version_host_software(
        self, output: str
    ) -> Optional[PensandoNicVersionHostSoftware]:
        """Parse 'nicctl show version host-software' output into PensandoNicVersionHostSoftware object.

        Args:
            output: Raw output from 'nicctl show version host-software' command

        Returns:
            PensandoNicVersionHostSoftware object or None if no data found
        """
        version_info = PensandoNicVersionHostSoftware()
        found_data = False

        for line in output.splitlines():
            line_stripped = line.strip()
            if not line_stripped or ":" not in line_stripped:
                continue

            # Split on the first colon to get key and value
            parts = line_stripped.split(":", 1)
            if len(parts) != 2:
                continue

            key = parts[0].strip().lower()
            value = parts[1].strip()

            if "nicctl" in key:
                version_info.nicctl = value
                found_data = True
            elif "ipc driver" in key or "ipc_driver" in key:
                version_info.ipc_driver = value
                found_data = True
            elif "ionic driver" in key or "ionic_driver" in key:
                version_info.ionic_driver = value
                found_data = True

        return version_info if found_data else None

    def _parse_nicctl_version_firmware(self, output: str) -> List[PensandoNicVersionFirmware]:
        """Parse 'nicctl show version firmware' output into PensandoNicVersionFirmware objects.

        Args:
            output: Raw output from 'nicctl show version firmware' command

        Returns:
            List of PensandoNicVersionFirmware objects
        """
        firmware_entries = []
        current_entry = None

        for line in output.splitlines():
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Skip separator lines (dashes)
            if re.match(r"^-+$", line_stripped):
                # Save previous entry when we hit a separator
                if current_entry:
                    firmware_entries.append(current_entry)
                    current_entry = None
                continue

            # Check for NIC line
            if line_stripped.startswith("NIC") and ":" in line_stripped:
                # Save previous entry if exists
                if current_entry:
                    firmware_entries.append(current_entry)

                # Parse NIC ID and PCIe BDF
                match = re.match(
                    r"NIC\s*:\s*([a-f0-9\-]+)\s*\(([0-9a-f:\.]+)\)", line_stripped, re.IGNORECASE
                )
                if match:
                    nic_id = match.group(1)
                    pcie_bdf = match.group(2)
                    current_entry = PensandoNicVersionFirmware(
                        nic_id=nic_id,
                        pcie_bdf=pcie_bdf,
                    )
                continue

            # Parse version fields
            if current_entry and ":" in line_stripped:
                parts = line_stripped.split(":", 1)
                if len(parts) == 2:
                    key = parts[0].strip().lower()
                    value = parts[1].strip()

                    if "cpld" in key:
                        current_entry.cpld = value
                    elif "boot0" in key:
                        current_entry.boot0 = value
                    elif "uboot-a" in key or "uboot_a" in key:
                        current_entry.uboot_a = value
                    elif "firmware-a" in key or "firmware_a" in key:
                        current_entry.firmware_a = value
                    elif (
                        "device config-a" in key
                        or "device_config_a" in key
                        or "device config" in key
                    ):
                        current_entry.device_config_a = value

        # Add the last entry if exists
        if current_entry:
            firmware_entries.append(current_entry)

        return firmware_entries

    def _parse_niccli_qos(self, device_num: int, output: str) -> BroadcomNicQos:
        """Parse 'niccli --dev X qos --ets --show' output into BroadcomNicQos object.

        Args:
            device_num: Device number
            output: Raw output from 'niccli --dev X qos --ets --show' command

        Returns:
            BroadcomNicQos object with parsed data
        """
        qos_info = BroadcomNicQos(device_num=device_num, raw_output=output)

        current_app_entry = None

        for line in output.splitlines():
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Parse PRIO_MAP: "PRIO_MAP: 0:0 1:0 2:0 3:1 4:0 5:0 6:0 7:2"
            if "PRIO_MAP:" in line:
                parts = line.split("PRIO_MAP:")
                if len(parts) >= 2:
                    prio_entries = parts[1].strip().split()
                    for entry in prio_entries:
                        if ":" in entry:
                            prio, tc = entry.split(":")
                            try:
                                qos_info.prio_map[int(prio)] = int(tc)
                            except ValueError:
                                pass

            # Parse TC Bandwidth: "TC Bandwidth: 50% 50% 0%"
            elif "TC Bandwidth:" in line:
                parts = line.split("TC Bandwidth:")
                if len(parts) >= 2:
                    bandwidth_entries = parts[1].strip().split()
                    for bw in bandwidth_entries:
                        bw_clean = bw.rstrip("%")
                        try:
                            qos_info.tc_bandwidth.append(int(bw_clean))
                        except ValueError:
                            pass

            # Parse TSA_MAP: "TSA_MAP: 0:ets 1:ets 2:strict"
            elif "TSA_MAP:" in line:
                parts = line.split("TSA_MAP:")
                if len(parts) >= 2:
                    tsa_entries = parts[1].strip().split()
                    for entry in tsa_entries:
                        if ":" in entry:
                            tc, tsa = entry.split(":", 1)
                            try:
                                qos_info.tsa_map[int(tc)] = tsa
                            except ValueError:
                                pass

            # Parse PFC enabled: "PFC enabled: 3"
            elif "PFC enabled:" in line:
                parts = line.split("PFC enabled:")
                if len(parts) >= 2:
                    try:
                        qos_info.pfc_enabled = int(parts[1].strip())
                    except ValueError:
                        pass

            # Parse APP entries - detect start of new APP entry
            elif line_stripped.startswith("APP#"):
                # Save previous entry if exists
                if current_app_entry:
                    qos_info.app_entries.append(current_app_entry)
                current_app_entry = BroadcomNicQosAppEntry()

            # Parse Priority within APP entry
            elif "Priority:" in line and current_app_entry is not None:
                parts = line.split("Priority:")
                if len(parts) >= 2:
                    try:
                        current_app_entry.priority = int(parts[1].strip())
                    except ValueError:
                        pass

            # Parse Sel within APP entry
            elif "Sel:" in line and current_app_entry is not None:
                parts = line.split("Sel:")
                if len(parts) >= 2:
                    try:
                        current_app_entry.sel = int(parts[1].strip())
                    except ValueError:
                        pass

            # Parse DSCP within APP entry
            elif "DSCP:" in line and current_app_entry is not None:
                parts = line.split("DSCP:")
                if len(parts) >= 2:
                    try:
                        current_app_entry.dscp = int(parts[1].strip())
                    except ValueError:
                        pass

            # Parse protocol and port (e.g., "UDP or DCCP: 4791")
            elif (
                "UDP" in line or "TCP" in line or "DCCP" in line
            ) and current_app_entry is not None:
                if ":" in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        current_app_entry.protocol = parts[0].strip()
                        try:
                            current_app_entry.port = int(parts[1].strip())
                        except ValueError:
                            pass

            # Parse TC Rate Limit: "TC Rate Limit: 100% 100% 100% 0% 0% 0% 0% 0%"
            elif "TC Rate Limit:" in line:
                parts = line.split("TC Rate Limit:")
                if len(parts) >= 2:
                    rate_entries = parts[1].strip().split()
                    for rate in rate_entries:
                        rate_clean = rate.rstrip("%")
                        try:
                            qos_info.tc_rate_limit.append(int(rate_clean))
                        except ValueError:
                            pass

        # Add the last APP entry if exists
        if current_app_entry:
            qos_info.app_entries.append(current_app_entry)

        return qos_info

    def _collect_ethtool_info(self, interfaces: List[NetworkInterface]) -> Dict[str, EthtoolInfo]:
        """Collect ethtool information for all network interfaces.

        Args:
            interfaces: List of NetworkInterface objects to collect ethtool info for

        Returns:
            Dictionary mapping interface name to EthtoolInfo
        """
        ethtool_data = {}

        for iface in interfaces:
            cmd = self.CMD_ETHTOOL_TEMPLATE.format(interface=iface.name)
            res_ethtool = self._run_sut_cmd(cmd, sudo=True)

            if res_ethtool.exit_code == 0:
                ethtool_info = self._parse_ethtool(iface.name, res_ethtool.stdout)
                ethtool_data[iface.name] = ethtool_info
                self._log_event(
                    category=EventCategory.NETWORK,
                    description=f"Collected ethtool info for interface: {iface.name}",
                    priority=EventPriority.INFO,
                )
            else:
                self._log_event(
                    category=EventCategory.NETWORK,
                    description=f"Error collecting ethtool info for interface: {iface.name}",
                    data={"command": res_ethtool.command, "exit_code": res_ethtool.exit_code},
                    priority=EventPriority.WARNING,
                )

        return ethtool_data

    def _collect_lldp_info(self) -> None:
        """Collect LLDP information using lldpcli and lldpctl commands."""
        # Run lldpcli show neighbor
        res_lldpcli = self._run_sut_cmd(self.CMD_LLDPCLI_NEIGHBOR, sudo=True)
        if res_lldpcli.exit_code == 0:
            self._log_event(
                category=EventCategory.NETWORK,
                description="Collected LLDP neighbor information (lldpcli)",
                priority=EventPriority.INFO,
            )
        else:
            self._log_event(
                category=EventCategory.NETWORK,
                description="LLDP neighbor collection failed or lldpcli not available",
                data={"command": res_lldpcli.command, "exit_code": res_lldpcli.exit_code},
                priority=EventPriority.INFO,
            )

        # Run lldpctl
        res_lldpctl = self._run_sut_cmd(self.CMD_LLDPCTL, sudo=True)
        if res_lldpctl.exit_code == 0:
            self._log_event(
                category=EventCategory.NETWORK,
                description="Collected LLDP information (lldpctl)",
                priority=EventPriority.INFO,
            )
        else:
            self._log_event(
                category=EventCategory.NETWORK,
                description="LLDP collection failed or lldpctl not available",
                data={"command": res_lldpctl.command, "exit_code": res_lldpctl.exit_code},
                priority=EventPriority.INFO,
            )

    def _collect_broadcom_nic_info(
        self,
    ) -> Tuple[List[BroadcomNicDevice], Dict[int, BroadcomNicQos]]:
        """Collect Broadcom NIC information using niccli commands.

        Returns:
            Tuple of (list of BroadcomNicDevice, dict mapping device number to BroadcomNicQos)
        """
        devices = []
        qos_data = {}

        # First, list devices
        res_listdev = self._run_sut_cmd(self.CMD_NICCLI_LISTDEV, sudo=True)
        if res_listdev.exit_code == 0:
            # Parse device list
            devices = self._parse_niccli_listdev(res_listdev.stdout)
            self._log_event(
                category=EventCategory.NETWORK,
                description=f"Collected Broadcom NIC device list: {len(devices)} devices",
                priority=EventPriority.INFO,
            )

            # Collect QoS info for each device
            for device in devices:
                cmd = self.CMD_NICCLI_GETQOS_TEMPLATE.format(device_num=device.device_num)
                res_qos = self._run_sut_cmd(cmd, sudo=True)
                if res_qos.exit_code == 0:
                    qos_info = self._parse_niccli_qos(device.device_num, res_qos.stdout)
                    qos_data[device.device_num] = qos_info
                    self._log_event(
                        category=EventCategory.NETWORK,
                        description=f"Collected Broadcom NIC QoS info for device {device.device_num}",
                        priority=EventPriority.INFO,
                    )
                else:
                    self._log_event(
                        category=EventCategory.NETWORK,
                        description=f"Failed to collect QoS info for device {device.device_num}",
                        data={"command": res_qos.command, "exit_code": res_qos.exit_code},
                        priority=EventPriority.WARNING,
                    )

            if qos_data:
                self._log_event(
                    category=EventCategory.NETWORK,
                    description=f"Collected Broadcom NIC QoS info for {len(qos_data)} devices",
                    priority=EventPriority.INFO,
                )
        else:
            self._log_event(
                category=EventCategory.NETWORK,
                description="Broadcom NIC collection failed or niccli not available",
                data={"command": res_listdev.command, "exit_code": res_listdev.exit_code},
                priority=EventPriority.INFO,
            )

        return devices, qos_data

    def _collect_pensando_nic_info(
        self,
    ) -> Tuple[
        List[PensandoNicCard],
        List[PensandoNicDcqcn],
        List[PensandoNicEnvironment],
        List[PensandoNicPcieAts],
        List[PensandoNicPort],
        List[PensandoNicQos],
        List[PensandoNicRdmaStatistics],
        Optional[PensandoNicVersionHostSoftware],
        List[PensandoNicVersionFirmware],
    ]:
        """Collect Pensando NIC information using nicctl commands.

        Returns:
            Tuple of (list of PensandoNicCard, list of PensandoNicDcqcn,
                     list of PensandoNicEnvironment, list of PensandoNicPcieAts,
                     list of PensandoNicPort, list of PensandoNicQos,
                     list of PensandoNicRdmaStatistics,
                     PensandoNicVersionHostSoftware object,
                     list of PensandoNicVersionFirmware)
        """
        cards = []
        dcqcn_entries = []
        environment_entries = []
        pcie_ats_entries = []
        port_entries = []
        qos_entries = []
        rdma_statistics_entries = []
        version_host_software = None
        version_firmware_entries = []
        collected_count = 0

        # Track which commands succeeded and which failed
        collected_commands = []
        uncollected_commands = []

        # Parse nicctl show card output
        cmd = "nicctl show card"
        res_card = self._run_sut_cmd(cmd, sudo=True)
        if res_card.exit_code == 0:
            cards = self._parse_nicctl_card(res_card.stdout)
            self._log_event(
                category=EventCategory.NETWORK,
                description=f"Collected Pensando NIC card list: {len(cards)} cards",
                priority=EventPriority.INFO,
            )
            collected_count += 1
            collected_commands.append(cmd)
        else:
            uncollected_commands.append(cmd)

        # Parse nicctl show dcqcn output
        cmd = "nicctl show dcqcn"
        res_dcqcn = self._run_sut_cmd(cmd, sudo=True)
        if res_dcqcn.exit_code == 0:
            dcqcn_entries = self._parse_nicctl_dcqcn(res_dcqcn.stdout)
            self._log_event(
                category=EventCategory.NETWORK,
                description=f"Collected Pensando NIC DCQCN info: {len(dcqcn_entries)} entries",
                priority=EventPriority.INFO,
            )
            collected_count += 1
            collected_commands.append(cmd)
        else:
            uncollected_commands.append(cmd)

        # Parse nicctl show environment output
        cmd = "nicctl show environment"
        res_environment = self._run_sut_cmd(cmd, sudo=True)
        if res_environment.exit_code == 0:
            environment_entries = self._parse_nicctl_environment(res_environment.stdout)
            self._log_event(
                category=EventCategory.NETWORK,
                description=f"Collected Pensando NIC environment info: {len(environment_entries)} entries",
                priority=EventPriority.INFO,
            )
            collected_count += 1
            collected_commands.append(cmd)
        else:
            uncollected_commands.append(cmd)

        # Parse nicctl show pcie ats output
        cmd = "nicctl show pcie ats"
        res_pcie_ats = self._run_sut_cmd(cmd, sudo=True)
        if res_pcie_ats.exit_code == 0:
            pcie_ats_entries = self._parse_nicctl_pcie_ats(res_pcie_ats.stdout)
            self._log_event(
                category=EventCategory.NETWORK,
                description=f"Collected Pensando NIC PCIe ATS info: {len(pcie_ats_entries)} entries",
                priority=EventPriority.INFO,
            )
            collected_count += 1
            collected_commands.append(cmd)
        else:
            uncollected_commands.append(cmd)

        # Parse nicctl show port output
        cmd = "nicctl show port"
        res_port = self._run_sut_cmd(cmd, sudo=True)
        if res_port.exit_code == 0:
            port_entries = self._parse_nicctl_port(res_port.stdout)
            self._log_event(
                category=EventCategory.NETWORK,
                description=f"Collected Pensando NIC port info: {len(port_entries)} ports",
                priority=EventPriority.INFO,
            )
            collected_count += 1
            collected_commands.append(cmd)
        else:
            uncollected_commands.append(cmd)

        # Parse nicctl show qos output
        cmd = "nicctl show qos"
        res_qos = self._run_sut_cmd(cmd, sudo=True)
        if res_qos.exit_code == 0:
            qos_entries = self._parse_nicctl_qos(res_qos.stdout)
            self._log_event(
                category=EventCategory.NETWORK,
                description=f"Collected Pensando NIC QoS info: {len(qos_entries)} entries",
                priority=EventPriority.INFO,
            )
            collected_count += 1
            collected_commands.append(cmd)
        else:
            uncollected_commands.append(cmd)

        # Parse nicctl show rdma statistics output
        cmd = "nicctl show rdma statistics"
        res_rdma_stats = self._run_sut_cmd(cmd, sudo=True)
        if res_rdma_stats.exit_code == 0:
            rdma_statistics_entries = self._parse_nicctl_rdma_statistics(res_rdma_stats.stdout)
            self._log_event(
                category=EventCategory.NETWORK,
                description=f"Collected Pensando NIC RDMA statistics: {len(rdma_statistics_entries)} entries",
                priority=EventPriority.INFO,
            )
            collected_count += 1
            collected_commands.append(cmd)
        else:
            uncollected_commands.append(cmd)

        # Parse nicctl show version host-software output
        cmd = "nicctl show version host-software"
        res_version_host = self._run_sut_cmd(cmd, sudo=True)
        if res_version_host.exit_code == 0:
            version_host_software = self._parse_nicctl_version_host_software(
                res_version_host.stdout
            )
            if version_host_software:
                self._log_event(
                    category=EventCategory.NETWORK,
                    description="Collected Pensando NIC host software version",
                    priority=EventPriority.INFO,
                )
                collected_count += 1
                collected_commands.append(cmd)
            else:
                uncollected_commands.append(cmd)
        else:
            uncollected_commands.append(cmd)

        # Parse nicctl show version firmware output
        cmd = "nicctl show version firmware"
        res_version_firmware = self._run_sut_cmd(cmd, sudo=True)
        if res_version_firmware.exit_code == 0:
            version_firmware_entries = self._parse_nicctl_version_firmware(
                res_version_firmware.stdout
            )
            self._log_event(
                category=EventCategory.NETWORK,
                description=f"Collected Pensando NIC firmware versions: {len(version_firmware_entries)} entries",
                priority=EventPriority.INFO,
            )
            collected_count += 1
            collected_commands.append(cmd)
        else:
            uncollected_commands.append(cmd)

        # Log summary of collected and uncollected commands
        if collected_commands:
            self._log_event(
                category=EventCategory.NETWORK,
                description=f"Successfully collected {len(collected_commands)} nicctl commands: {', '.join(collected_commands)}",
                priority=EventPriority.INFO,
            )

        if uncollected_commands:
            self._log_event(
                category=EventCategory.NETWORK,
                description=f"Failed to collect {len(uncollected_commands)} nicctl commands: {', '.join(uncollected_commands)}",
                priority=EventPriority.WARNING,
            )

        if not collected_commands and not uncollected_commands:
            self._log_event(
                category=EventCategory.NETWORK,
                description="Pensando NIC collection failed or nicctl not available",
                priority=EventPriority.INFO,
            )

        return (
            cards,
            dcqcn_entries,
            environment_entries,
            pcie_ats_entries,
            port_entries,
            qos_entries,
            rdma_statistics_entries,
            version_host_software,
            version_firmware_entries,
        )

    def collect_data(
        self,
        args=None,
    ) -> Tuple[TaskResult, Optional[NetworkDataModel]]:
        """Collect network configuration from the system.

        Returns:
            Tuple[TaskResult, Optional[NetworkDataModel]]: tuple containing the task result
            and an instance of NetworkDataModel or None if collection failed.
        """
        interfaces = []
        routes = []
        rules = []
        neighbors = []
        ethtool_data = {}
        broadcom_devices: List[BroadcomNicDevice] = []
        broadcom_qos_data: Dict[int, BroadcomNicQos] = {}
        pensando_cards: List[PensandoNicCard] = []
        pensando_dcqcn: List[PensandoNicDcqcn] = []
        pensando_environment: List[PensandoNicEnvironment] = []
        pensando_pcie_ats: List[PensandoNicPcieAts] = []
        pensando_ports: List[PensandoNicPort] = []
        pensando_qos: List[PensandoNicQos] = []
        pensando_rdma_statistics: List[PensandoNicRdmaStatistics] = []
        pensando_version_host_software: Optional[PensandoNicVersionHostSoftware] = None
        pensando_version_firmware: List[PensandoNicVersionFirmware] = []

        # Collect interface/address information
        res_addr = self._run_sut_cmd(self.CMD_ADDR)
        if res_addr.exit_code == 0:
            interfaces = self._parse_ip_addr(res_addr.stdout)
            self._log_event(
                category=EventCategory.NETWORK,
                description=f"Collected {len(interfaces)} network interfaces",
                priority=EventPriority.INFO,
            )
        else:
            self._log_event(
                category=EventCategory.NETWORK,
                description="Error collecting network interfaces",
                data={"command": res_addr.command, "exit_code": res_addr.exit_code},
                priority=EventPriority.ERROR,
                console_log=True,
            )

        # Collect ethtool information for interfaces
        if interfaces:
            ethtool_data = self._collect_ethtool_info(interfaces)
            self._log_event(
                category=EventCategory.NETWORK,
                description=f"Collected ethtool info for {len(ethtool_data)} interfaces",
                priority=EventPriority.INFO,
            )

        # Collect routing table
        res_route = self._run_sut_cmd(self.CMD_ROUTE)
        if res_route.exit_code == 0:
            routes = self._parse_ip_route(res_route.stdout)
            self._log_event(
                category=EventCategory.NETWORK,
                description=f"Collected {len(routes)} routes",
                priority=EventPriority.INFO,
            )
        else:
            self._log_event(
                category=EventCategory.NETWORK,
                description="Error collecting routes",
                data={"command": res_route.command, "exit_code": res_route.exit_code},
                priority=EventPriority.WARNING,
            )

        # Collect routing rules
        res_rule = self._run_sut_cmd(self.CMD_RULE)
        if res_rule.exit_code == 0:
            rules = self._parse_ip_rule(res_rule.stdout)
            self._log_event(
                category=EventCategory.NETWORK,
                description=f"Collected {len(rules)} routing rules",
                priority=EventPriority.INFO,
            )
        else:
            self._log_event(
                category=EventCategory.NETWORK,
                description="Error collecting routing rules",
                data={"command": res_rule.command, "exit_code": res_rule.exit_code},
                priority=EventPriority.WARNING,
            )

        # Collect neighbor table (ARP/NDP)
        res_neighbor = self._run_sut_cmd(self.CMD_NEIGHBOR)
        if res_neighbor.exit_code == 0:
            neighbors = self._parse_ip_neighbor(res_neighbor.stdout)
            self._log_event(
                category=EventCategory.NETWORK,
                description=f"Collected {len(neighbors)} neighbor entries",
                priority=EventPriority.INFO,
            )
        else:
            self._log_event(
                category=EventCategory.NETWORK,
                description="Error collecting neighbor table",
                data={"command": res_neighbor.command, "exit_code": res_neighbor.exit_code},
                priority=EventPriority.WARNING,
            )

        # Collect LLDP information
        self._collect_lldp_info()

        # Collect Broadcom NIC information
        broadcom_devices, broadcom_qos_data = self._collect_broadcom_nic_info()

        # Collect Pensando NIC information
        (
            pensando_cards,
            pensando_dcqcn,
            pensando_environment,
            pensando_pcie_ats,
            pensando_ports,
            pensando_qos,
            pensando_rdma_statistics,
            pensando_version_host_software,
            pensando_version_firmware,
        ) = self._collect_pensando_nic_info()

        network_data = NetworkDataModel(
            interfaces=interfaces,
            routes=routes,
            rules=rules,
            neighbors=neighbors,
            ethtool_info=ethtool_data,
            broadcom_nic_devices=broadcom_devices,
            broadcom_nic_qos=broadcom_qos_data,
            pensando_nic_cards=pensando_cards,
            pensando_nic_dcqcn=pensando_dcqcn,
            pensando_nic_environment=pensando_environment,
            pensando_nic_pcie_ats=pensando_pcie_ats,
            pensando_nic_ports=pensando_ports,
            pensando_nic_qos=pensando_qos,
            pensando_nic_rdma_statistics=pensando_rdma_statistics,
            pensando_nic_version_host_software=pensando_version_host_software,
            pensando_nic_version_firmware=pensando_version_firmware,
        )
        self.result.message = (
            f"Collected network data: {len(interfaces)} interfaces, "
            f"{len(routes)} routes, {len(rules)} rules, {len(neighbors)} neighbors, "
            f"{len(ethtool_data)} ethtool entries, {len(broadcom_devices)} Broadcom NICs, "
            f"{len(pensando_cards)} Pensando NICs, {len(pensando_dcqcn)} Pensando DCQCN entries, "
            f"{len(pensando_environment)} Pensando environment entries, "
            f"{len(pensando_pcie_ats)} Pensando PCIe ATS entries, "
            f"{len(pensando_ports)} Pensando ports, "
            f"{len(pensando_qos)} Pensando QoS entries, "
            f"{len(pensando_rdma_statistics)} Pensando RDMA statistics, "
            f"Pensando host software version: {'Yes' if pensando_version_host_software else 'No'}, "
            f"{len(pensando_version_firmware)} Pensando firmware versions"
        )
        self.result.status = ExecutionStatus.OK
        return self.result, network_data
