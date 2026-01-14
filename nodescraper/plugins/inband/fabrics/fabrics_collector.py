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

from .fabricsdata import (
    FabricsDataModel,
    IbdevNetdevMapping,
    IbstatDevice,
    IbvDeviceInfo,
    MstDevice,
    MstStatus,
    OfedInfo,
    RdmaDevice,
    RdmaInfo,
    RdmaLink,
)


class FabricsCollector(InBandDataCollector[FabricsDataModel, None]):
    """Collect InfiniBand/RDMA fabrics configuration details"""

    DATA_MODEL = FabricsDataModel
    CMD_IBSTAT = "ibstat"
    CMD_IBV_DEVINFO = "ibv_devinfo"
    CMD_IB_DEV_NETDEVS = "ls -l /sys/class/infiniband/*/device/net"
    CMD_OFED_INFO = "ofed_info -s"
    CMD_MST_START = "mst start"
    CMD_MST_STATUS = "mst status -v"
    CMD_RDMA_DEV = "rdma dev"
    CMD_RDMA_LINK = "rdma link"

    def _parse_ibstat(self, output: str) -> List[IbstatDevice]:
        """Parse 'ibstat' output into IbstatDevice objects.

        Args:
            output: Raw output from 'ibstat' command

        Returns:
            List of IbstatDevice objects
        """
        devices = []
        current_device = None
        current_port = None
        current_port_attrs: Dict[str, str] = {}

        for line in output.splitlines():
            line_stripped = line.strip()

            # CA name line (e.g., "CA 'mlx5_0'")
            if line.startswith("CA "):
                # Save previous device if exists
                if current_device:
                    devices.append(current_device)

                # Extract CA name
                match = re.search(r"CA\s+'([^']+)'", line)
                if match:
                    ca_name = match.group(1)
                    current_device = IbstatDevice(ca_name=ca_name, raw_output=output)
                    current_port = None
                    current_port_attrs = {}

            # Port line (e.g., "Port 1:")
            elif line.startswith("Port ") and ":" in line:
                # Save previous port if exists
                if current_device and current_port is not None:
                    current_device.ports[current_port] = current_port_attrs

                # Extract port number
                match = re.search(r"Port\s+(\d+):", line)
                if match:
                    current_port = int(match.group(1))
                    current_port_attrs = {}

            # Attribute lines (indented with key: value format)
            elif ":" in line_stripped and current_device:
                parts = line_stripped.split(":", 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()

                    # Store port-specific attributes
                    if current_port is not None:
                        current_port_attrs[key] = value
                    else:
                        # Store device-level attributes
                        if key == "CA type":
                            current_device.ca_type = value
                        elif key == "Number of ports":
                            try:
                                current_device.number_of_ports = int(value)
                            except ValueError:
                                pass
                        elif key == "Firmware version":
                            current_device.firmware_version = value
                        elif key == "Hardware version":
                            current_device.hardware_version = value
                        elif key == "Node GUID":
                            current_device.node_guid = value
                        elif key == "System image GUID":
                            current_device.system_image_guid = value

        # Save last device and port
        if current_device:
            if current_port is not None:
                current_device.ports[current_port] = current_port_attrs
            devices.append(current_device)

        return devices

    def _parse_ibv_devinfo(self, output: str) -> List[IbvDeviceInfo]:
        """Parse 'ibv_devinfo' output into IbvDeviceInfo objects.

        Args:
            output: Raw output from 'ibv_devinfo' command

        Returns:
            List of IbvDeviceInfo objects
        """
        devices = []
        current_device = None
        current_port = None
        current_port_attrs: Dict[str, str] = {}

        for line in output.splitlines():
            line_stripped = line.strip()

            # Device header (e.g., "hca_id:	mlx5_0")
            if line.startswith("hca_id:"):
                # Save previous device if exists
                if current_device:
                    devices.append(current_device)

                parts = line.split(":", 1)
                if len(parts) == 2:
                    device_name = parts[1].strip()
                    current_device = IbvDeviceInfo(device=device_name, raw_output=output)
                    current_port = None
                    current_port_attrs = {}

            # Port line (e.g., "port:	1")
            elif line_stripped.startswith("port:") and current_device:
                # Save previous port if exists
                if current_port is not None:
                    current_device.ports[current_port] = current_port_attrs

                parts = line_stripped.split(":", 1)
                if len(parts) == 2:
                    try:
                        current_port = int(parts[1].strip())
                        current_port_attrs = {}
                    except ValueError:
                        pass

            # Attribute lines (with key: value format)
            elif ":" in line_stripped and current_device:
                parts = line_stripped.split(":", 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value = parts[1].strip()

                    # Store port-specific attributes
                    if current_port is not None:
                        current_port_attrs[key] = value
                    else:
                        # Store device-level attributes
                        if key == "node_guid":
                            current_device.node_guid = value
                        elif key == "sys_image_guid":
                            current_device.sys_image_guid = value
                        elif key == "vendor_id":
                            current_device.vendor_id = value
                        elif key == "vendor_part_id":
                            current_device.vendor_part_id = value
                        elif key == "hw_ver":
                            current_device.hw_ver = value
                        elif key == "fw_ver":
                            current_device.fw_ver = value
                        elif key == "node_type":
                            current_device.node_type = value
                        elif key == "transport_type" or key == "transport":
                            current_device.transport_type = value

        # Save last device and port
        if current_device:
            if current_port is not None:
                current_device.ports[current_port] = current_port_attrs
            devices.append(current_device)

        return devices

    def _parse_ib_dev_netdevs(self, output: str) -> List[IbdevNetdevMapping]:
        """Parse 'ls -l /sys/class/infiniband/*/device/net' output into IbdevNetdevMapping objects.

        Args:
            output: Raw output from 'ls -l /sys/class/infiniband/*/device/net' command

        Returns:
            List of IbdevNetdevMapping objects
        """
        mappings = []
        current_ib_device = None

        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue

            # Check if this is a directory path line
            # Example: /sys/class/infiniband/rocep105s0/device/net:
            if line.startswith("/sys/class/infiniband/") and line.endswith(":"):
                # Extract IB device name from path
                path_match = re.search(r"/sys/class/infiniband/([^/]+)/device/net:", line)
                if path_match:
                    current_ib_device = path_match.group(1)
                continue

            # Skip "total" lines
            if line.startswith("total"):
                continue

            # Parse directory listing lines (network device names)
            # Example: drwxr-xr-x 5 root root 0 Jan  8 18:01 benic5p1
            if current_ib_device and line.startswith("d"):
                parts = line.split()
                if len(parts) >= 9:
                    # The last part is the network device name
                    netdev = parts[-1]

                    # Create mapping with default port 1 (most common for single-port devices)
                    # State is unknown from ls output
                    mapping = IbdevNetdevMapping(
                        ib_device=current_ib_device, port=1, netdev=netdev, state=None
                    )
                    mappings.append(mapping)

        return mappings

    def _parse_ofed_info(self, output: str) -> OfedInfo:
        """Parse 'ofed_info -s' output into OfedInfo object.

        Args:
            output: Raw output from 'ofed_info -s' command

        Returns:
            OfedInfo object
        """
        version = None

        # The output is typically just a version string, possibly with trailing colon
        # Example: OFED-internal-25.10-1.7.1:
        output_stripped = output.strip()
        if output_stripped:
            # Remove trailing colon if present
            version = output_stripped.rstrip(":")

        return OfedInfo(version=version, raw_output=output)

    def _parse_mst_status(self, output: str) -> MstStatus:
        """Parse 'mst status -v' output into MstStatus object.

        Args:
            output: Raw output from 'mst status -v' command

        Returns:
            MstStatus object
        """
        mst_status = MstStatus(raw_output=output)
        devices = []

        # Check if MST is started
        if "MST modules:" in output or "MST devices:" in output or "PCI devices:" in output:
            mst_status.mst_started = True

        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue

            # Skip header lines
            if (
                line.startswith("MST modules:")
                or line.startswith("PCI devices:")
                or line.startswith("---")
            ):
                continue
            if line.startswith("DEVICE_TYPE") or line.startswith("MST PCI module"):
                continue

            # Look for device lines containing "/dev/mst/"
            if "/dev/mst/" in line:
                parts = line.split()

                # Handle old format: "/dev/mst/device_path" at the beginning
                if line.startswith("/dev/mst/"):
                    device_path = parts[0]
                    device = MstDevice(device=device_path)

                    # Try to parse additional fields (old format with key=value)
                    for part in parts[1:]:
                        if "=" in part:
                            key, value = part.split("=", 1)
                            if key == "rdma":
                                device.rdma_device = value
                            elif key == "net":
                                device.net_device = value
                            elif ":" in value and "." in value:
                                device.pci_address = value
                            else:
                                device.attributes[key] = value
                        elif re.match(r"[0-9a-f]{2,4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9]", part):
                            device.pci_address = part

                    devices.append(device)

                # Handle new tabular format: DEVICE_TYPE MST PCI RDMA NET NUMA [VFIO]
                # Example: ConnectX7(rev:0) /dev/mst/mt4129_pciconf9 ec:00.0 mlx5_4 net-enp235s0np0 1
                else:
                    # Find the index of the /dev/mst/ device path
                    mst_idx = None
                    for i, part in enumerate(parts):
                        if part.startswith("/dev/mst/"):
                            mst_idx = i
                            break

                    if mst_idx is not None and len(parts) >= mst_idx + 3:
                        device_path = parts[mst_idx]
                        device = MstDevice(device=device_path)

                        # Store device type if available (before mst path)
                        if mst_idx > 0:
                            device.attributes["device_type"] = " ".join(parts[:mst_idx])

                        # PCI address (next column after MST path)
                        if mst_idx + 1 < len(parts):
                            pci_addr = parts[mst_idx + 1]
                            # Validate PCI address format (short or long form)
                            if re.match(r"[0-9a-f]{2,4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9]", pci_addr):
                                device.pci_address = pci_addr

                        # RDMA device (column after PCI)
                        if mst_idx + 2 < len(parts):
                            rdma_dev = parts[mst_idx + 2]
                            if rdma_dev.startswith("mlx") or rdma_dev != "-":
                                device.rdma_device = rdma_dev

                        # NET device (column after RDMA)
                        if mst_idx + 3 < len(parts):
                            net_dev = parts[mst_idx + 3]
                            # Remove "net-" prefix if present
                            if net_dev.startswith("net-"):
                                net_dev = net_dev[4:]
                            if net_dev != "-":
                                device.net_device = net_dev

                        # NUMA node (column after NET)
                        if mst_idx + 4 < len(parts):
                            numa = parts[mst_idx + 4]
                            if numa.isdigit():
                                device.attributes["numa_node"] = numa

                        # VFIO or other attributes (remaining columns)
                        if mst_idx + 5 < len(parts):
                            device.attributes["vfio"] = " ".join(parts[mst_idx + 5 :])

                        devices.append(device)

        mst_status.devices = devices
        return mst_status

    def _parse_rdma_dev(self, output: str) -> List[RdmaDevice]:
        """Parse 'rdma dev' output into RdmaDevice objects.

        Args:
            output: Raw output from 'rdma dev' command

        Returns:
            List of RdmaDevice objects
        """
        devices = []

        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue

            # Example InfiniBand format: 0: mlx5_0: node_type ca fw 16.28.2006 node_guid 0c42:a103:00b3:bfa0 sys_image_guid 0c42:a103:00b3:bfa0
            # Example RoCE format: 0: rocep9s0: node_type ca fw 1.117.1-a-63 node_guid 0690:81ff:fe4a:6c40 sys_image_guid 0690:81ff:fe4a:6c40
            parts = line.split()
            if len(parts) < 2:
                continue

            # First part might be index followed by colon
            device_name = None
            start_idx = 0

            if parts[0].endswith(":"):
                # Skip index (e.g., "0:")
                start_idx = 1

            if start_idx < len(parts):
                device_name = parts[start_idx].rstrip(":")
                start_idx += 1

            if not device_name:
                continue

            device = RdmaDevice(device=device_name)

            # Parse remaining attributes
            i = start_idx
            while i < len(parts):
                if parts[i] == "node_type" and i + 1 < len(parts):
                    device.node_type = parts[i + 1]
                    i += 2
                elif parts[i] == "fw" and i + 1 < len(parts):
                    device.attributes["fw_version"] = parts[i + 1]
                    i += 2
                elif parts[i] == "node_guid" and i + 1 < len(parts):
                    device.node_guid = parts[i + 1]
                    i += 2
                elif parts[i] == "sys_image_guid" and i + 1 < len(parts):
                    device.sys_image_guid = parts[i + 1]
                    i += 2
                elif parts[i] == "state" and i + 1 < len(parts):
                    device.state = parts[i + 1]
                    i += 2
                else:
                    # Store as generic attribute
                    if i + 1 < len(parts) and not parts[i + 1].startswith("-"):
                        device.attributes[parts[i]] = parts[i + 1]
                        i += 2
                    else:
                        i += 1

            devices.append(device)

        return devices

    def _parse_rdma_link(self, output: str) -> List[RdmaLink]:
        """Parse 'rdma link' output into RdmaLink objects.

        Args:
            output: Raw output from 'rdma link' command

        Returns:
            List of RdmaLink objects
        """
        links = []

        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue

            # Example InfiniBand format: link mlx5_0/1 state ACTIVE physical_state LINK_UP netdev ib0
            # Example RoCE format: link rocep9s0/1 state DOWN physical_state POLLING netdev benic8p1
            # Example alternate format: 0/1: mlx5_0/1: state ACTIVE physical_state LINK_UP
            match = re.search(r"(\S+)/(\d+)", line)
            if not match:
                continue

            device_name = match.group(1)
            port = int(match.group(2))

            link = RdmaLink(device=device_name, port=port)

            # Parse remaining attributes
            parts = line.split()
            i = 0
            while i < len(parts):
                if parts[i] == "state" and i + 1 < len(parts):
                    link.state = parts[i + 1]
                    i += 2
                elif parts[i] == "physical_state" and i + 1 < len(parts):
                    link.physical_state = parts[i + 1]
                    i += 2
                elif parts[i] == "netdev" and i + 1 < len(parts):
                    link.netdev = parts[i + 1]
                    i += 2
                else:
                    # Store as generic attribute if it's a key-value pair
                    if i + 1 < len(parts) and not parts[i + 1].startswith("-"):
                        link.attributes[parts[i]] = parts[i + 1]
                        i += 2
                    else:
                        i += 1

            links.append(link)

        return links

    def collect_data(
        self,
        args=None,
    ) -> Tuple[TaskResult, Optional[FabricsDataModel]]:
        """Collect InfiniBand/RDMA fabrics configuration from the system.

        Returns:
            Tuple[TaskResult, Optional[FabricsDataModel]]: tuple containing the task result
            and an instance of FabricsDataModel or None if collection failed.
        """
        ibstat_devices = []
        ibv_devices = []
        ibdev_netdev_mappings = []
        ofed_info = None
        mst_status = None
        rdma_info = None

        # Collect ibstat information
        res_ibstat = self._run_sut_cmd(self.CMD_IBSTAT)
        if res_ibstat.exit_code == 0:
            ibstat_devices = self._parse_ibstat(res_ibstat.stdout)
            self._log_event(
                category=EventCategory.NETWORK,
                description=f"Collected {len(ibstat_devices)} IB devices from ibstat",
                priority=EventPriority.INFO,
            )
        else:
            self._log_event(
                category=EventCategory.NETWORK,
                description="Error collecting ibstat information",
                data={"command": res_ibstat.command, "exit_code": res_ibstat.exit_code},
                priority=EventPriority.WARNING,
            )

        # Collect ibv_devinfo information
        res_ibv = self._run_sut_cmd(self.CMD_IBV_DEVINFO)
        if res_ibv.exit_code == 0:
            ibv_devices = self._parse_ibv_devinfo(res_ibv.stdout)
            self._log_event(
                category=EventCategory.NETWORK,
                description=f"Collected {len(ibv_devices)} IB devices from ibv_devinfo",
                priority=EventPriority.INFO,
            )
        else:
            self._log_event(
                category=EventCategory.NETWORK,
                description="ibv_devinfo command not available or failed",
                data={"command": res_ibv.command, "exit_code": res_ibv.exit_code},
                priority=EventPriority.INFO,
            )

        # Collect IB device to netdev mappings
        res_ib_dev_netdevs = self._run_sut_cmd(self.CMD_IB_DEV_NETDEVS)
        if res_ib_dev_netdevs.exit_code == 0:
            ibdev_netdev_mappings = self._parse_ib_dev_netdevs(res_ib_dev_netdevs.stdout)
            self._log_event(
                category=EventCategory.NETWORK,
                description=f"Collected {len(ibdev_netdev_mappings)} IB to netdev mappings",
                priority=EventPriority.INFO,
            )
        else:
            self._log_event(
                category=EventCategory.NETWORK,
                description="No InfiniBand devices found in sysfs",
                data={
                    "command": res_ib_dev_netdevs.command,
                    "exit_code": res_ib_dev_netdevs.exit_code,
                },
                priority=EventPriority.INFO,
            )

        # Collect OFED version info
        res_ofed = self._run_sut_cmd(self.CMD_OFED_INFO)
        if res_ofed.exit_code == 0:
            ofed_info = self._parse_ofed_info(res_ofed.stdout)
            self._log_event(
                category=EventCategory.NETWORK,
                description=f"Collected OFED version: {ofed_info.version}",
                priority=EventPriority.INFO,
            )
        else:
            self._log_event(
                category=EventCategory.NETWORK,
                description="OFED not installed or ofed_info command not available",
                data={"command": res_ofed.command, "exit_code": res_ofed.exit_code},
                priority=EventPriority.INFO,
            )

        # Start MST and collect status
        # First start MST
        res_mst_start = self._run_sut_cmd(self.CMD_MST_START, sudo=True)
        if res_mst_start.exit_code == 0:
            # Check output for success indicators
            output_lower = res_mst_start.stdout.lower()
            if "success" in output_lower or "loading mst" in output_lower:
                self._log_event(
                    category=EventCategory.NETWORK,
                    description="MST service started successfully",
                    priority=EventPriority.INFO,
                )
            else:
                self._log_event(
                    category=EventCategory.NETWORK,
                    description="MST service command completed but status unclear",
                    data={"output": res_mst_start.stdout[:200]},
                    priority=EventPriority.INFO,
                )
        else:
            self._log_event(
                category=EventCategory.NETWORK,
                description="MST tools not available (Mellanox-specific)",
                data={"command": res_mst_start.command, "exit_code": res_mst_start.exit_code},
                priority=EventPriority.INFO,
            )

        # Get MST status
        res_mst_status = self._run_sut_cmd(self.CMD_MST_STATUS, sudo=True)
        if res_mst_status.exit_code == 0:
            mst_status = self._parse_mst_status(res_mst_status.stdout)
            self._log_event(
                category=EventCategory.NETWORK,
                description=f"Collected MST status: {len(mst_status.devices)} devices",
                priority=EventPriority.INFO,
            )
        else:
            self._log_event(
                category=EventCategory.NETWORK,
                description="MST status not available (Mellanox-specific)",
                data={"command": res_mst_status.command, "exit_code": res_mst_status.exit_code},
                priority=EventPriority.INFO,
            )

        # Collect RDMA device information
        rdma_devices = []
        res_rdma_dev = self._run_sut_cmd(self.CMD_RDMA_DEV)
        if res_rdma_dev.exit_code == 0:
            rdma_devices = self._parse_rdma_dev(res_rdma_dev.stdout)
            self._log_event(
                category=EventCategory.NETWORK,
                description=f"Collected {len(rdma_devices)} RDMA devices",
                priority=EventPriority.INFO,
            )
        else:
            self._log_event(
                category=EventCategory.NETWORK,
                description="Error collecting RDMA device information",
                data={"command": res_rdma_dev.command, "exit_code": res_rdma_dev.exit_code},
                priority=EventPriority.WARNING,
            )

        # Collect RDMA link information
        rdma_links = []
        res_rdma_link = self._run_sut_cmd(self.CMD_RDMA_LINK)
        if res_rdma_link.exit_code == 0:
            rdma_links = self._parse_rdma_link(res_rdma_link.stdout)
            self._log_event(
                category=EventCategory.NETWORK,
                description=f"Collected {len(rdma_links)} RDMA links",
                priority=EventPriority.INFO,
            )
        else:
            self._log_event(
                category=EventCategory.NETWORK,
                description="Error collecting RDMA link information",
                data={"command": res_rdma_link.command, "exit_code": res_rdma_link.exit_code},
                priority=EventPriority.WARNING,
            )

        # Combine RDMA information
        if rdma_devices or rdma_links:
            rdma_info = RdmaInfo(
                devices=rdma_devices,
                links=rdma_links,
                raw_output=res_rdma_dev.stdout + "\n" + res_rdma_link.stdout,
            )

        # Build the data model only if we collected any data
        if (
            ibstat_devices
            or ibv_devices
            or ibdev_netdev_mappings
            or ofed_info
            or mst_status
            or rdma_info
        ):
            fabrics_data = FabricsDataModel(
                ibstat_devices=ibstat_devices,
                ibv_devices=ibv_devices,
                ibdev_netdev_mappings=ibdev_netdev_mappings,
                ofed_info=ofed_info,
                mst_status=mst_status,
                rdma_info=rdma_info,
            )
            self.result.message = (
                f"Collected fabrics data: {len(ibstat_devices)} ibstat devices, "
                f"{len(ibv_devices)} ibv devices, {len(ibdev_netdev_mappings)} mappings, "
                f"OFED: {ofed_info.version if ofed_info else 'N/A'}, "
                f"MST devices: {len(mst_status.devices) if mst_status else 0}, "
                f"RDMA devices: {len(rdma_info.devices) if rdma_info else 0}"
            )
            self.result.status = ExecutionStatus.OK
            return self.result, fabrics_data
        else:
            # No fabrics hardware detected - this is not an error for optional hardware
            self.result.message = "No InfiniBand/RDMA fabrics hardware detected on this system"
            self.result.status = ExecutionStatus.ERROR
            return self.result, None
