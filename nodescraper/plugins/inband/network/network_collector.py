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
            # Format: "1 ) Broadcom BCM57608 1x400G QSFP-DD PCIe Ethernet NIC (Adp#1 Port#1)"
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

    def _collect_pensando_nic_info(self) -> None:
        """Collect Pensando NIC information using nicctl commands."""
        collected_count = 0
        for cmd in self.CMD_NICCTL_COMMANDS:
            res = self._run_sut_cmd(cmd, sudo=True)
            if res.exit_code == 0:
                collected_count += 1

        if collected_count > 0:
            self._log_event(
                category=EventCategory.NETWORK,
                description=f"Collected Pensando NIC information ({collected_count} commands)",
                priority=EventPriority.INFO,
            )
        else:
            self._log_event(
                category=EventCategory.NETWORK,
                description="Pensando NIC collection failed or nicctl not available",
                priority=EventPriority.INFO,
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
        self._collect_pensando_nic_info()

        if interfaces or routes or rules or neighbors or broadcom_devices:
            network_data = NetworkDataModel(
                interfaces=interfaces,
                routes=routes,
                rules=rules,
                neighbors=neighbors,
                ethtool_info=ethtool_data,
                broadcom_nic_devices=broadcom_devices,
                broadcom_nic_qos=broadcom_qos_data,
            )
            self.result.message = (
                f"Collected network data: {len(interfaces)} interfaces, "
                f"{len(routes)} routes, {len(rules)} rules, {len(neighbors)} neighbors, "
                f"{len(ethtool_data)} ethtool entries, {len(broadcom_devices)} Broadcom NICs"
            )
            self.result.status = ExecutionStatus.OK
            return self.result, network_data
        else:
            self.result.message = "Failed to collect network data"
            self.result.status = ExecutionStatus.ERROR
            return self.result, None
