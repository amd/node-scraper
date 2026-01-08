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
    CMD_IBDEV2NETDEV = "ibdev2netdev -v"
    CMD_OFED_INFO = "/usr/bin/ofed_info -s"
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

    def _parse_ibdev2netdev(self, output: str) -> List[IbdevNetdevMapping]:
        """Parse 'ibdev2netdev -v' output into IbdevNetdevMapping objects.

        Args:
            output: Raw output from 'ibdev2netdev -v' command

        Returns:
            List of IbdevNetdevMapping objects
        """
        mappings = []

        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue

            # Example format: mlx5_0 port 1 ==> ib0 (Up)
            # Example format: mlx5_1 port 1 ==> N/A (Down)
            match = re.match(r"(\S+)\s+port\s+(\d+)\s+==>\s+(\S+)\s+\(([^)]+)\)", line)
            if match:
                ib_device = match.group(1)
                port = int(match.group(2))
                netdev = match.group(3) if match.group(3) != "N/A" else None
                state = match.group(4)

                mapping = IbdevNetdevMapping(
                    ib_device=ib_device, port=port, netdev=netdev, state=state
                )
                mappings.append(mapping)

        return mappings

    def _parse_ofed_info(self, output: str) -> OfedInfo:
        """Parse '/usr/bin/ofed_info -s' output into OfedInfo object.

        Args:
            output: Raw output from 'ofed_info -s' command

        Returns:
            OfedInfo object
        """
        version = None

        # The output is typically just a version string
        output_stripped = output.strip()
        if output_stripped:
            version = output_stripped

        return OfedInfo(version=version, raw_output=output)

    def _parse_mst_status(self, output: str) -> MstStatus:
        """Parse 'sudo mst status -v' output into MstStatus object.

        Args:
            output: Raw output from 'mst status -v' command

        Returns:
            MstStatus object
        """
        mst_status = MstStatus(raw_output=output)
        devices = []

        # Check if MST is started
        if "MST modules:" in output or "MST devices:" in output:
            mst_status.mst_started = True

        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue

            # Look for device lines (e.g., "/dev/mst/mt4123_pciconf0")
            if line.startswith("/dev/mst/"):
                parts = line.split()
                if parts:
                    device_path = parts[0]
                    device = MstDevice(device=device_path)

                    # Try to parse additional fields
                    for part in parts[1:]:
                        if "=" in part:
                            key, value = part.split("=", 1)
                            if key == "rdma":
                                device.rdma_device = value
                            elif key == "net":
                                device.net_device = value
                            elif ":" in value and "." in value:
                                # Looks like a PCI address
                                device.pci_address = value
                            else:
                                device.attributes[key] = value
                        elif re.match(r"[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-9]", part):
                            # PCI address format
                            device.pci_address = part

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

            # Example format: 0: mlx5_0: node_type ca fw 16.28.2006 node_guid 0c42:a103:00b3:bfa0 sys_image_guid 0c42:a103:00b3:bfa0
            parts = line.split()
            if len(parts) < 2:
                continue

            # First part might be index followed by colon
            device_name = None
            start_idx = 0

            if parts[0].endswith(":"):
                # Skip index
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

            # Example format: link mlx5_0/1 state ACTIVE physical_state LINK_UP netdev ib0
            # Example format: 0/1: mlx5_0/1: state ACTIVE physical_state LINK_UP
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
                description="Error collecting ibv_devinfo information",
                data={"command": res_ibv.command, "exit_code": res_ibv.exit_code},
                priority=EventPriority.WARNING,
            )

        # Collect ibdev2netdev mappings
        res_ibdev2netdev = self._run_sut_cmd(self.CMD_IBDEV2NETDEV)
        if res_ibdev2netdev.exit_code == 0:
            ibdev_netdev_mappings = self._parse_ibdev2netdev(res_ibdev2netdev.stdout)
            self._log_event(
                category=EventCategory.NETWORK,
                description=f"Collected {len(ibdev_netdev_mappings)} IB to netdev mappings",
                priority=EventPriority.INFO,
            )
        else:
            self._log_event(
                category=EventCategory.NETWORK,
                description="Error collecting ibdev2netdev mappings",
                data={
                    "command": res_ibdev2netdev.command,
                    "exit_code": res_ibdev2netdev.exit_code,
                },
                priority=EventPriority.WARNING,
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
                description="Error collecting OFED info",
                data={"command": res_ofed.command, "exit_code": res_ofed.exit_code},
                priority=EventPriority.WARNING,
            )

        # Start MST and collect status
        # First start MST
        res_mst_start = self._run_sut_cmd(self.CMD_MST_START, sudo=True)
        if res_mst_start.exit_code == 0:
            self._log_event(
                category=EventCategory.NETWORK,
                description="MST service started successfully",
                priority=EventPriority.INFO,
            )
        else:
            self._log_event(
                category=EventCategory.NETWORK,
                description="Error starting MST service (might already be running)",
                data={"command": res_mst_start.command, "exit_code": res_mst_start.exit_code},
                priority=EventPriority.WARNING,
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
                description="Error collecting MST status",
                data={"command": res_mst_status.command, "exit_code": res_mst_status.exit_code},
                priority=EventPriority.WARNING,
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

        # Build the data model if we collected any data
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
            self.result.message = "Failed to collect fabrics data"
            self.result.status = ExecutionStatus.ERROR
            return self.result, None
