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
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Union

from pydantic import ValidationError

from nodescraper.base import InBandDataCollector
from nodescraper.connection.inband import TextFileArtifact
from nodescraper.enums import (
    EventCategory,
    EventPriority,
    ExecutionStatus,
    OSFamily,
    SystemInteractionLevel,
)
from nodescraper.models import TaskResult
from nodescraper.utils import get_all_subclasses, get_exception_details

from .collector_args import PcieCollectorArgs
from .pcie_data import (
    MAX_CAP_ID,
    MAX_ECAP_ID,
    CapabilityEnum,
    ExtendedCapabilityEnum,
    PcieCapStructure,
    PcieCfgSpace,
    PcieDataModel,
    Type0Configuration,
    Type1Configuration,
)


class PcieCollector(InBandDataCollector[PcieDataModel, PcieCollectorArgs]):
    """class for collection of PCIe data only supports Linux OS type.

    This class collects the PCIE config space using the lspci hex dump and then parses the hex dump to get the
    PCIe configuration space for the GPUs in the system. If the system interaction level is set to STANDARD or higher,
    then the entire pcie configuration space is collected for the GPUs in the system. If the system interaction level
    is set to SURFACE then, only the first 64 bytes of the pcie configuration space is collected for the GPUs in the system.

    This class will collect important PCIe data from the system running the commands
    - `lspci -vvv` : Verbose collection of PCIe data
    - `lspci -vvvt`: Verbose tree view of PCIe data
    - `lspci -PP`: Path view of PCIe data for the GPUs
    - `lspci -PP -D`: Path view of PCIe data for the GPUs (with domain prefix)
    - If system interaction level is set to STANDARD or higher, the following commands will be run with sudo:
        - `lspci -xxxx`: Hex view of PCIe data for the GPUs
    - otherwise the following commands will be run without sudo:
        - `lspci -x`: Hex view of PCIe data for the GPUs
    - `lspci -d <vendor_id>:` : Detect AMD GPU device IDs in the system
    - `lspci -PP -D -d <vendor_id>:<dev_id>` : Upstream BDF path for GPUs (with domain prefix)
    - If system interaction level is set to STANDARD or higher, the following commands will be run with sudo:
        - The sudo lspci -xxxx command is used to collect the PCIe configuration space for the GPUs in the system
    - otherwise the following commands will be run without sudo:
        - The lspci -x command is used to collect the PCIe configuration space for the GPUs in the system
    - If collect_all_devices is set, non-AMD devices are also collected:
        - `lspci -D -nn`: Enumerate every PCI device
        - `find -L /sys/bus/pci/devices -maxdepth 2 -name physfn`: Identify SR-IOV VFs so they are excluded
        - Config space is parsed from the `lspci -x`/`lspci -xxxx` dump above

    """

    SUPPORTED_OS_FAMILY: Set[OSFamily] = {OSFamily.LINUX}

    DATA_MODEL = PcieDataModel

    CMD_LSPCI_VERBOSE = "lspci -vvv"
    CMD_LSPCI_VERBOSE_TREE = "lspci -vvvt"
    CMD_LSPCI_PATH = "lspci -PP"
    CMD_LSPCI_PATH_DOMAIN = "lspci -PP -D"
    CMD_LSPCI_HEX_SUDO = "lspci -xxxx"
    CMD_LSPCI_HEX = "lspci -x"
    CMD_LSPCI_AMD_DEVICES = "lspci -d {vendor_id}: -nn"
    CMD_LSPCI_ALL_DEVICES = "lspci -D -nn"
    # Every SR-IOV VF has a physfn link back to its PF. -L follows the
    # /sys/bus/pci/devices symlinks.
    CMD_LIST_VFS = "find -L /sys/bus/pci/devices -maxdepth 2 -name physfn"
    CMD_LSPCI_PATH_DEVICE = "lspci -PP -d {vendor_id}:{dev_id}"
    CMD_LSPCI_PATH_DEVICE_DOMAIN = "lspci -PP -D -d {vendor_id}:{dev_id}"

    def _detect_amd_device_ids(self) -> dict[str, list[str]]:
        """Detect AMD GPU device IDs from the system using lspci.

        Returns:
            dict[str, list[str]]: Dictionary with 'vendor_id', 'device_ids', and 'vf_device_ids'
        """
        vendor_id_hex = format(self.system_info.vendorid_ep, "x")
        result: dict[str, list[str]] = {
            "vendor_id": [vendor_id_hex],
            "device_ids": [],
            "vf_device_ids": [],
        }

        res = self._run_sut_cmd(
            self.CMD_LSPCI_AMD_DEVICES.format(vendor_id=vendor_id_hex),
            sudo=False,
            log_artifact=False,
        )
        if res.exit_code == 0 and res.stdout:
            # Pattern: [vendor:device]
            device_id_pattern = rf"\[{vendor_id_hex}:([0-9a-fA-F]{{4}})\]"
            # Pattern to detect VF in description
            vf_pattern = r"Virtual Function"

            for line in res.stdout.splitlines():
                matches = re.findall(device_id_pattern, line)
                if matches:
                    device_id = matches[0].lower()
                    # Check if it's a VF
                    if re.search(vf_pattern, line, re.IGNORECASE):
                        if device_id not in result["vf_device_ids"]:
                            result["vf_device_ids"].append(device_id)
                            self.logger.info(f"Detected AMD VF device ID: {device_id}")
                    else:
                        if device_id not in result["device_ids"]:
                            result["device_ids"].append(device_id)
                            self.logger.info(f"Detected AMD device ID: {device_id}")

        self._log_event(
            category=EventCategory.IO,
            description="Detected AMD GPU device IDs from system",
            data=result,
            priority=EventPriority.INFO,
        )

        return result

    def _detect_vf_bdfs(self) -> Set[str]:
        """Return the domain-qualified BDFs of all SR-IOV Virtual Functions.

        Returns
        -------
        Set[str]
            BDFs of VFs. Empty if there are none or sysfs could not be read.
        """
        res = self._run_sut_cmd(self.CMD_LIST_VFS, sudo=False, log_artifact=False)
        vf_bdfs: Set[str] = set()
        # find can exit non-zero for unrelated unreadable entries, so parse stdout regardless.
        for line in (res.stdout or "").splitlines():
            # Format: "/sys/bus/pci/devices/0000:03:00.2/physfn"
            parts = line.strip().split("/")
            if len(parts) >= 2 and parts[-1] == "physfn":
                vf_bdfs.add(parts[-2])
        return vf_bdfs

    def _detect_other_devices(self) -> Optional[List[str]]:
        """Detect non-AMD PCI devices in the system using lspci.

        Enumerates every PCI device with ``lspci -D -nn`` and returns the
        domain-qualified BDFs of devices whose vendor ID is NOT the AMD
        endpoint vendor (``self.system_info.vendorid_ep``). AMD devices are
        skipped because ``_get_pcie_data`` already collects them, and SR-IOV
        Virtual Functions are skipped so they aren't counted as devices.

        Returns
        -------
        Optional[List[str]]
            A list of domain-qualified BDFs for non-AMD PCI devices, or None if
            the devices could not be enumerated.
        """
        vendor_id_hex = format(self.system_info.vendorid_ep, "x")
        other_bdfs: List[str] = []

        res = self._run_sut_cmd(
            self.CMD_LSPCI_ALL_DEVICES,
            sudo=False,
            log_artifact=False,
        )
        if res.exit_code != 0 or not res.stdout:
            self._log_event(
                category=EventCategory.IO,
                description="Failed to enumerate PCI devices",
                data={
                    "command": self.CMD_LSPCI_ALL_DEVICES,
                    "exit_code": res.exit_code,
                    "stderr": res.stderr,
                },
                priority=EventPriority.ERROR,
            )
            return None

        vf_bdfs = self._detect_vf_bdfs()
        skipped_vfs: List[str] = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            # Format: "0000:02:00.0 Ethernet controller [0200]: Intel ... [8086:1572]"
            bdf = line.split()[0]
            # Skip AMD endpoints (already handled by the AMD-specific path)
            if f"[{vendor_id_hex}:" in line.lower():
                continue
            if bdf in vf_bdfs or "virtual function" in line.lower():
                skipped_vfs.append(bdf)
                continue
            other_bdfs.append(bdf)

        self._log_event(
            category=EventCategory.IO,
            description="Detected non-AMD PCI devices from system",
            data={
                "other_device_count": len(other_bdfs),
                "bdfs": other_bdfs,
                "skipped_vf_count": len(skipped_vfs),
            },
            priority=EventPriority.INFO,
        )

        return other_bdfs

    def show_lspci_verbose(self, sudo=True) -> Optional[str]:
        """Show lspci with -vvv."""
        return self._run_os_cmd(self.CMD_LSPCI_VERBOSE, sudo=sudo)

    def show_lspci_verbose_tree(self, sudo=True) -> Optional[str]:
        """Show lspci with -vvvt (verbose tree view)."""
        return self._run_os_cmd(self.CMD_LSPCI_VERBOSE_TREE, sudo=sudo)

    def show_lspci_path(self, sudo=True) -> Optional[str]:
        """Show lspci with -PP."""
        return self._run_os_cmd(self.CMD_LSPCI_PATH, sudo=sudo)

    def show_lspci_path_domain(self, sudo=True) -> Optional[str]:
        """Show lspci with -PP -D (path view with domain prefix)."""
        return self._run_os_cmd(self.CMD_LSPCI_PATH_DOMAIN, sudo=sudo)

    def show_lspci_hex(self, bdf: Optional[str] = None, sudo=True) -> Optional[str]:
        """Show lspci with -xxxx."""
        if sudo:
            hex_arg = "-xxxx"
        else:
            # Sudo required for whole pcie configuration space
            hex_arg = "-x"

        if bdf:
            return self._run_os_cmd(f"lspci {hex_arg} -s {bdf}", sudo=sudo)
        return self._run_os_cmd(f"lspci {hex_arg}", sudo=sudo)

    def _run_os_cmd(
        self, command: str, sudo: bool = True, ignore_error: bool = False
    ) -> Optional[str]:
        """Run os command. Run as sudo by default.

         Args:
            command (str): command to run on the OS
            sudo (bool): run as sudo or not
            ignore_error (bool): ignore error or not
        Returns:
            stdout: str
        """
        cmd_ret = self._run_sut_cmd(command, sudo=sudo)
        if ignore_error:
            return cmd_ret.stdout
        elif cmd_ret.stderr != "" or cmd_ret.exit_code != 0:
            return None
        else:
            return cmd_ret.stdout

    def _get_upstream_bdf_from_buspath(
        self,
        vendor_id: str,
        dev_id: str,
        upstream_steps_limit: Optional[int] = 0,
        sudo=True,
    ) -> Optional[Dict[str, List[str]]]:
        """Get all the upstream BDFs for a vendor/device id.

        Parameters
        ----------
        vendor_id : str
            A pcie vendor id
        dev_id : str
            A pcie device id
        upstream_steps_limit : Optional[int]
            The limit on the number of upstream devices to collect, by default 0
        sudo : bool
            Run the command as sudo or not, by default True

        Returns
        -------
        Optional[List[str]]
            A list of upstream BDFs or None on failure
        """
        split_bdf_pos = 0

        bus_path_all_gpus = self._run_os_cmd(
            self.CMD_LSPCI_PATH_DEVICE_DOMAIN.format(vendor_id=vendor_id, dev_id=dev_id),
            sudo=sudo,
        )
        if bus_path_all_gpus is None or bus_path_all_gpus == "":
            self._log_event(
                category=EventCategory.IO,
                description="Failed to get bus path info for vendor/device ID.",
                data={"vendor_id": vendor_id, "dev_id": dev_id},
                priority=EventPriority.INFO,
            )
            return None
        upstream_bdfs: Dict[str, List[str]] = {}
        for bus_path in bus_path_all_gpus.splitlines():
            bus_path_list = (bus_path.split(" ")[split_bdf_pos]).split("/")
            # With -D, only the first path component carries the domain prefix (e.g. 0001:00:01.1).
            # Propagate it to all downstream bare BDFs so config space reads hit the correct domain.
            domain = "0000"
            for component in bus_path_list:
                if component.count(":") == 2:
                    domain = component.split(":")[0]
                    break
            bus_path_list = [
                f"{domain}:{bdf}" if bdf.count(":") == 1 else bdf for bdf in bus_path_list
            ]
            if upstream_steps_limit is not None and len(bus_path_list) < upstream_steps_limit + 1:
                # We don't have enough upstream devices to collect
                self._log_event(
                    category=EventCategory.RUNTIME,
                    description="Not enough upstream devices found.",
                    data={
                        "bus_path": bus_path,
                        "upstream_steps_limit": upstream_steps_limit,
                        "bus_path_list": bus_path_list,
                    },
                    priority=EventPriority.WARNING,
                )
            bdf_str = bus_path_list[-1]
            upstream_bdfs[bdf_str] = []
            # Flip the bus_path_list to get GPU first and then upstream devices
            bus_path_list.reverse()
            # Upstream + 1 to always include GPU and # of upstream devices
            if upstream_steps_limit is None:
                upstream_bdfs[bdf_str] = bus_path_list
            else:
                for bdf in range(min(len(bus_path_list), upstream_steps_limit + 1)):
                    upstream_bdfs[bdf_str].append(bus_path_list[bdf])

        return upstream_bdfs

    def _get_gpu_cfg_space(
        self,
        vendor_id: str,
        device_id: str,
        upstream_steps_from_gpu: Optional[int] = 0,
        sudo=True,
    ) -> dict[str, PcieCfgSpace]:
        """
        - Generates a nested dictionary with the PCIe configuration space for the bdfs corresponding to the vendor/device ID
        - Populates the dict by reading cfg space through 'setpci' commands

        Args:
            vendor_id (str): vendor ID (hex format)
            device_id (str): device ID (hex format)
            upstream_steps_from_gpu (Optional[int]): The number of upstream devices to collect the PCIe cfg space for, by default 0
        Returns:
            all_bdf_cfg_space_dict: nested dictionary containing PCIe cfg space for all bdfs corresponding to the vendor/device ID
        """
        if (vendor_id is None) or (device_id is None):
            self._log_event(
                category=EventCategory.IO,
                description="System info is invalid Vendor ID or Device ID is None.",
                data={"vendor_id": vendor_id, "dev_id": device_id},
                priority=EventPriority.ERROR,
            )
            return {}

        bdf_list = self._get_upstream_bdf_from_buspath(
            vendor_id,
            device_id,
            upstream_steps_limit=upstream_steps_from_gpu,
            sudo=sudo,
        )
        if bdf_list is None:
            return {}

        all_bdf_cfg_space_dict = {}
        for gpu_bdf_list in bdf_list.values():
            for bdf in gpu_bdf_list:
                new_base_dict = self.get_cfg_by_bdf(bdf, sudo=sudo)
                all_bdf_cfg_space_dict[bdf] = new_base_dict
        return all_bdf_cfg_space_dict

    def parse_hex_dump(self, hex_dump: str) -> list[int]:
        """Parse the hex dump."""

        hex_dump = hex_dump.strip()
        byte_list = []
        for line in hex_dump.splitlines():
            parts = line.split(":")
            if len(parts) != 2:
                continue  # Skip malformed lines
            if len(parts[1]) != 48:
                continue  # Unexpected number of bytes
            byte_str = parts[1]
            tokens = byte_str.strip().split()
            for token in tokens:
                byte = int(token, 16)
                byte_list.append(byte)

        return byte_list

    def read_register(self, width: int, offset: int, config_data: List[int]):
        """Read a register from the hex dump, width should be 1, 2, 4, or 8 bytes"""
        register_value = 0
        for i in range(0, width >> 3):
            register_value += config_data[offset + i] << (i * 8)
        return register_value

    def extended_cap_finder(
        self,
        config_data: List[int],
        cap_pointer: int,
        cap_data: Optional[Dict[int, int]] = None,
    ):
        """Obtain capability structure by parsing the hex dump for capability pointers

        config_data : List[int]
            A list of int's representing the hex dump from lspci -x or sudo lspci -xxxx
        cap_pointer : int
            The hex value of a Capability pointer or 0x34 for the first cap pointer
        cap_data : Optional[dict[int, int]], optional
            A dictionary of capability pointers, by default None

        returns
        -------
        cap_data : Dict[int, int]
            A list of capability pointers, key is the cap_id and value is the cap_pointer use CapabilityEnum(cap_id) to get the Name
        """
        if cap_data is None:
            cap_data = {}
        if cap_pointer >= len(config_data) or cap_pointer + 1 >= len(config_data):
            # prevent an illegal access to the list
            return cap_data
        cap_id = config_data[cap_pointer] + (config_data[cap_pointer + 1] << 8)
        if cap_id > MAX_ECAP_ID:
            # Break if the cap_id is greater than the max extended cap id
            self._log_event(
                category=EventCategory.IO,
                description=f"Invalid Capability ID detected {cap_id}",
                priority=EventPriority.ERROR,
                data={"cap_id": cap_id},
            )
            return {}
        cap_data[cap_id] = cap_pointer
        if cap_pointer + 3 >= len(config_data):
            return cap_data
        next_cap_pointer = (config_data[cap_pointer + 2] & 0xF0) >> 4
        next_cap_pointer += config_data[cap_pointer + 3] << 4
        if next_cap_pointer == 0:
            return cap_data
        else:
            return self.extended_cap_finder(config_data, next_cap_pointer, cap_data)

    def cap_finder(
        self,
        config_data: List[int],
        cap_pointer: int,
        cap_data: Optional[Dict[int, int]] = None,
    ):
        """Obtain capability structure by parsing the hex dump for capability pointers

        Parameters
        ----------
        config_data : List[int]
            A list of int's representing the hex dump from lspci -xxxx
        cap_pointer : int
            The hex value of a Capability pointer or 0x34 for the first cap pointer
        cap_data : Optional[Dict[int, int]], optional
            A dictionary of capability pointers, by default None

        Returns
        -------
        cap_data : Dict[int, int]
            A list of extended apability pointers, key is the cap_id and value is the cap_pointer use ExtendedCapabilityEnum(cap_id) to get the Name
        """
        if cap_data is None:
            cap_data = {}

        if cap_pointer == 0x34:
            # Special case for ths first cap pointer, this one doesn't have an associated cap_id so just move on
            return self.cap_finder(config_data, config_data[0x34], cap_data)
        if cap_pointer >= len(config_data) or cap_pointer + 1 >= len(config_data):
            # prevent an illegal access to the list
            return cap_data
        cap_id = config_data[cap_pointer]
        if cap_id > MAX_CAP_ID:
            # Break if the cap_id is greater than the max cap id
            self._log_event(
                category=EventCategory.IO,
                description=f"Invalid Capability ID detected {cap_id}",
                priority=EventPriority.ERROR,
                data={"cap_id": cap_id},
            )
            return {}
        next_cap_pointer = config_data[cap_pointer + 1]
        cap_data[cap_id] = cap_pointer
        if next_cap_pointer == 0:
            return cap_data
        else:
            return self.cap_finder(config_data, next_cap_pointer, cap_data)

    def get_cap_struct(self, id: Enum) -> Optional[type[PcieCapStructure]]:
        for cap_struct in get_all_subclasses(PcieCapStructure):
            if cap_struct.cap_id == id:
                return cap_struct
        return None

    def get_pcie_common_cfg(
        self,
        type_x_configuration: Union[type[Type0Configuration], type[Type1Configuration]],
        config_data: List[int],
    ) -> Union[Type0Configuration, Type1Configuration]:
        """Get the Base PCIe configuration space from the hex dump items

        Parameters
        ----------
        type_x_configuration : Union[type[Type0Configuration], type[Type1Configuration]]
            Either Type0Configuration or Type1Configuration
        config_data : List[int]
             Config data from lspci -xxxx

        Returns
        -------
        Union[Type0Configuration, Type1Configuration]
            The complete model that was input
        """
        register_data: Dict[str, int] = {}
        type_x_obj = type_x_configuration()
        for register_name, register_in in type_x_obj.iter_regs():
            register = register_in.model_copy()
            register_data[register_name] = self.read_register(
                register.width, register.offset, config_data
            )
        type_x_obj.set_regs(register_data)
        return type_x_obj

    def get_cap_cfg(
        self,
        cap_data: Dict[int, int],
        config_data: List[int],
    ) -> Union[
        Dict[CapabilityEnum, PcieCapStructure], Dict[ExtendedCapabilityEnum, PcieCapStructure]
    ]:
        """Get the data from the capability structures

        Parameters
        ----------
        cap_data : Dict[int,int]
            A list of capability pointers, key is the cap_id and value is the cap_pointer
        config_data : List[int]
            A list of ints representing the hex dump from lspci -xxxx

        Returns
        -------
        Union[Dict[CapabilityEnum, PcieCapStructure], Dict[ExtendedCapabilityEnum, PcieCapStructure]]
            Either a dict of CapabilityEnum to PcieCapStructure or ExtendedCapabilityEnum to PcieCapStructure

        """
        cap_structure: Dict[Enum, PcieCapStructure] = {}
        for cap_id, cap_addr in cap_data.items():
            if cap_id == 0:
                continue
            cap_type = ExtendedCapabilityEnum if cap_addr >= 0x100 else CapabilityEnum
            try:
                cap_enum: Enum = cap_type(cap_id)
            except ValueError:
                # Unknown / not-yet-modeled capability id. Skip it instead of
                # aborting the whole collection so one new cap id can't take
                # down the entire PCIe plugin.
                self.logger.warning(
                    "Skipping unknown %s id 0x%X at offset 0x%X",
                    cap_type.__name__,
                    cap_id,
                    cap_addr,
                )
                continue
            cap_cls = self.get_cap_struct(cap_enum)
            if cap_cls is None:
                continue
            cap_obj = cap_cls()  # type: ignore[call-arg]
            reg_data = {}
            for register_name, register in cap_obj.iter_regs():
                reg_data[register_name] = self.read_register(
                    register.width, register.offset + cap_addr, config_data
                )
            cap_obj.set_regs(reg_data)
            cap_obj.offset = cap_addr
            cap_structure[cap_enum] = cap_obj

        return cap_structure  # type: ignore[return-value]

    def get_cfg_by_bdf(self, bdf: str, sudo=True) -> PcieCfgSpace:
        """Will fill out a PcieCfgSpace object with the PCIe configuration space for a given BDF"""
        cfg_space = self._parse_cfg_space(bdf, self.show_lspci_hex(bdf, sudo=sudo))
        return cfg_space if cfg_space is not None else PcieCfgSpace()

    def _parse_cfg_space(self, bdf: str, hex_data_raw: Optional[str]) -> Optional[PcieCfgSpace]:
        """Parse an lspci hex dump for a single BDF into a PcieCfgSpace.

        Returns None, after logging an event, when the dump is missing or too short.
        """
        if hex_data_raw is None:
            self._log_event(
                category=EventCategory.IO,
                description="Failed to get hex data for BDF.",
                data={"bdf": bdf},
                priority=EventPriority.ERROR,
            )
            return None
        hex_data: List[int] = self.parse_hex_dump(hex_data_raw)
        if len(hex_data) < 64:
            # Expect at least 256 bytes of data, for the first 256 bytes of the PCIe config space
            self._log_event(
                category=EventCategory.IO,
                description="Hex data is not the expected length",
                data={"bdf": bdf, "length": len(hex_data)},
                priority=EventPriority.ERROR,
            )
            return None
        cap_data, ecap_data = self.discover_capability_structure(hex_data)
        return self.get_pcie_cfg(hex_data, cap_data, ecap_data)

    def get_pcie_cfg(
        self,
        config_data: List[int],
        cap_data: Dict[int, int],
        ecap_data: Dict[int, int],
    ) -> PcieCfgSpace:
        """Gets the pcie config space from a list of ints

        Parameters
        ----------
        config_data : List[int]
            A list of ints representing the hex dump from lspci -xxxx
        cap_data : Dict[int, int]
            A list of capability pointers, key is the cap_id and value is the cap_pointer

        Returns
        -------
        PcieCfgSpace
            A PcieCfgSpace object with the PCIe configuration
        """
        type0 = self.get_pcie_common_cfg(Type0Configuration, config_data)
        type1 = self.get_pcie_common_cfg(Type1Configuration, config_data)
        cap = self.get_cap_cfg(cap_data, config_data)
        ecap = self.get_cap_cfg(ecap_data, config_data)
        return PcieCfgSpace(
            type_0_configuration=type0,  # type: ignore[arg-type]
            type_1_configuration=type1,  # type: ignore[arg-type]
            capability_pointers=cap_data,  # type: ignore[arg-type]
            extended_capability_pointers=ecap_data,  # type: ignore[arg-type]
            cap_structure=cap,  # type: ignore[arg-type]
            ecap_structure=ecap,  # type: ignore[arg-type]
        )

    def _log_pcie_artifacts(
        self,
        lspci_pp: Optional[str],
        lspci_pp_d: Optional[str],
        lspci_hex: Optional[str],
        lspci_verbose_tree: Optional[str],
        lspci_verbose: Optional[str],
    ):
        """Log the file artifacts for the PCIe data collector."""
        name_log_map = {
            "lspci_hex.txt": lspci_hex,
            "lspci_verbose_tree.txt": lspci_verbose_tree,
            "lspci_verbose.txt": lspci_verbose,
            "lspci_pp.txt": lspci_pp,
            "lspci_pp_d.txt": lspci_pp_d,
        }
        for name, data in name_log_map.items():
            if data is not None:
                self.result.artifacts.append(TextFileArtifact(filename=name, contents=data))

    # Header line of one device in a full lspci hex dump, e.g. "02:00.0 Ethernet ..."
    # or "0000:02:00.0 Ethernet ...". Hex rows ("00: 86 80 ...") don't match.
    _LSPCI_HEX_HEADER_RE = re.compile(
        r"^((?:[0-9a-fA-F]{4}:)?[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7])\s"
    )

    def _split_lspci_hex_dump(self, lspci_hex: str) -> Dict[str, str]:
        """Split a full ``lspci -x``/``lspci -xxxx`` dump into one dump per device.

        Parameters
        ----------
        lspci_hex : str
            Output of ``lspci -x`` or ``lspci -xxxx`` for all devices.

        Returns
        -------
        Dict[str, str]
            Mapping of domain-qualified BDF to that device's hex dump.
        """
        dumps: Dict[str, List[str]] = {}
        current: Optional[List[str]] = None
        for line in lspci_hex.splitlines():
            header = self._LSPCI_HEX_HEADER_RE.match(line)
            if header:
                bdf = header.group(1)
                # lspci omits the domain on systems that only have domain 0000.
                if bdf.count(":") == 1:
                    bdf = f"0000:{bdf}"
                current = dumps.setdefault(bdf.lower(), [])
            elif current is not None:
                current.append(line)
        return {bdf: "\n".join(lines) for bdf, lines in dumps.items()}

    def _get_other_cfg_space(
        self,
        bdfs: List[str],
        already_collected: Set[str],
        lspci_hex: Optional[str],
        sudo: bool,
    ) -> Dict[str, PcieCfgSpace]:
        """Collect config space for non-AMD devices.

        Config space is parsed from the full lspci hex dump when the device is
        in it, so no extra command is run per device. A per-device lspci call
        is only made for devices missing from the dump.

        Parameters
        ----------
        bdfs : List[str]
            Domain-qualified BDFs to collect.
        already_collected : Set[str]
            BDFs already collected on the AMD path (e.g. root ports and
            switches upstream of the GPUs). These are skipped so they are not
            collected or reported twice.
        lspci_hex : Optional[str]
            Full ``lspci -x``/``lspci -xxxx`` dump, or None if it failed.
        sudo : bool
            Whether per-device fallback reads use sudo.

        Returns
        -------
        Dict[str, PcieCfgSpace]
            Config space per BDF. Devices whose config space could not be read
            are left out.
        """
        dump_by_bdf = self._split_lspci_hex_dump(lspci_hex) if lspci_hex else {}
        cfg_spaces: Dict[str, PcieCfgSpace] = {}
        for bdf in bdfs:
            if bdf in already_collected:
                continue
            hex_data_raw = dump_by_bdf.get(bdf.lower())
            if hex_data_raw is None:
                hex_data_raw = self.show_lspci_hex(bdf, sudo=sudo)
            cfg_space = self._parse_cfg_space(bdf, hex_data_raw)
            if cfg_space is not None:
                cfg_spaces[bdf] = cfg_space
        return cfg_spaces

    def _get_pcie_data(
        self,
        upstream_steps_to_collect: Optional[int] = None,
        collect_all_devices: bool = False,
    ) -> Optional[PcieDataModel]:
        """Will return all PCIe data in a PcieDataModel object.

        Parameters
        ----------
        upstream_steps_to_collect : Optional[int]
            Number of upstream devices to collect config space for, by default None
        collect_all_devices : bool
            When True, also collect config space for non-AMD PCI devices into
            ``other_pcie_cfg_space``, by default False

        Returns
        -------
        Optional[PcieDataModel]
            The data in a PcieDataModel object or None on failure
        """
        minimum_system_interaction_level_required_for_sudo = SystemInteractionLevel.INTERACTIVE

        try:
            if (
                isinstance(self.system_interaction_level, SystemInteractionLevel)
                and self.system_interaction_level
                >= minimum_system_interaction_level_required_for_sudo
            ):
                use_sudo = True
            else:
                use_sudo = False

            if upstream_steps_to_collect is None:
                upstream_steps_to_collect = None

            # Detect AMD device IDs dynamically from the system
            detected_devices = self._detect_amd_device_ids()
            vendor_id = (
                detected_devices["vendor_id"][0]
                if detected_devices["vendor_id"]
                else format(self.system_info.vendorid_ep, "x")
            )
            device_ids = detected_devices["device_ids"]
            vf_device_ids = detected_devices["vf_device_ids"]

            pcie_cfg_dict: Dict[str, PcieCfgSpace] = {}
            vf_pcie_cfg_data: Dict[str, PcieCfgSpace] = {}

            # Collect PCIe config space for each detected device ID
            for dev_id in device_ids:
                cfg_space = self._get_gpu_cfg_space(
                    vendor_id=vendor_id,
                    device_id=dev_id,
                    upstream_steps_from_gpu=upstream_steps_to_collect,
                    sudo=use_sudo,
                )
                if cfg_space:
                    pcie_cfg_dict.update(cfg_space)

            # Collect VF PCIe config space for each detected VF device ID
            for dev_id_vf in vf_device_ids:
                vf_cfg_space = self._get_gpu_cfg_space(
                    vendor_id=vendor_id,
                    device_id=dev_id_vf,
                    upstream_steps_from_gpu=0,
                    sudo=use_sudo,
                )
                if vf_cfg_space:
                    vf_pcie_cfg_data.update(vf_cfg_space)

            lspci_hex = self.show_lspci_hex(sudo=use_sudo)

            # Optionally collect config space for non-AMD PCI devices.
            # Stays None when not requested or when enumeration fails, so the
            # analyzer can tell "not collected" apart from "none found".
            other_pcie_cfg_data: Optional[Dict[str, PcieCfgSpace]] = None
            if collect_all_devices:
                other_bdfs = self._detect_other_devices()
                if other_bdfs is not None:
                    other_pcie_cfg_data = self._get_other_cfg_space(
                        other_bdfs,
                        already_collected=set(pcie_cfg_dict) | set(vf_pcie_cfg_data),
                        lspci_hex=lspci_hex,
                        sudo=use_sudo,
                    )

            lspci_verbose = self.show_lspci_verbose(sudo=use_sudo)
            lspci_verbose_tree = self.show_lspci_verbose_tree(sudo=use_sudo)
            lspci_path = self.show_lspci_path(sudo=use_sudo)
            lspci_path_domain = self.show_lspci_path_domain(sudo=use_sudo)
            self._log_pcie_artifacts(
                lspci_pp=lspci_path,
                lspci_pp_d=lspci_path_domain,
                lspci_hex=lspci_hex,
                lspci_verbose_tree=lspci_verbose_tree,
                lspci_verbose=lspci_verbose,
            )
            pcie_data = PcieDataModel(
                pcie_cfg_space=pcie_cfg_dict,
                vf_pcie_cfg_space=vf_pcie_cfg_data,
                other_pcie_cfg_space=other_pcie_cfg_data,
            )
        except ValidationError as e:
            self._log_event(
                category=EventCategory.OS,
                description="Failed to build model for PCIe data",
                data=get_exception_details(e),
                priority=EventPriority.ERROR,
            )
            self.result.status = ExecutionStatus.ERROR
            return None
        return pcie_data

    def discover_capability_structure(
        self, hex_dump: List[int]
    ) -> Tuple[Dict[int, int], Dict[int, int]]:
        """Obtain the capability structure by parsing the hex dump for capability pointers

        Parameters
        ----------
        hex_dump : List[int]
            A list of ints from lspci -xxxx

        Returns
        -------
        dict[int, int]
            A list of capability pointers, key is the cap_id and value is the cap_pointer
        """
        cap = self.cap_finder(hex_dump, 0x34)
        ecap = self.extended_cap_finder(hex_dump, 0x100)
        return cap, ecap

    def collect_data(
        self,
        args: Optional[PcieCollectorArgs] = None,
    ) -> Tuple[TaskResult, Optional[PcieDataModel]]:
        """Read PCIe data.

        Args:
            args: Optional collector arguments. Defaults to PcieCollectorArgs(),
                which collects the full upstream path of AMD devices only.

        Returns:
            Tuple[TaskResult, Optional[PcieDataModel]]: tuple containing the result of the task and the PCIe data if available
        """
        if args is None:
            args = PcieCollectorArgs()

        pcie_data = self._get_pcie_data(
            args.upstream_steps_to_collect,
            collect_all_devices=args.collect_all_devices,
        )
        if pcie_data:
            self._log_event(
                category=EventCategory.IO,
                description="PCIe Data read from GPUs",
                data={
                    "bdf_count": len(pcie_data.pcie_cfg_space.keys()),
                    "other_bdf_count": (
                        len(pcie_data.other_pcie_cfg_space) if pcie_data.other_pcie_cfg_space else 0
                    ),
                },
                priority=EventPriority.INFO,
            )
        return self.result, pcie_data
