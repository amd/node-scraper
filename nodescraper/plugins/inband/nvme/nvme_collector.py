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
import json
import os
import re
from typing import Optional

from pydantic import ValidationError

from nodescraper.base import InBandDataCollector
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult
from nodescraper.utils import bytes_to_human_readable, str_or_none

from .nvmedata import NvmeDataModel, NvmeListEntry


class NvmeCollector(InBandDataCollector[NvmeDataModel, None]):
    """Collect NVMe details from the system."""

    DATA_MODEL = NvmeDataModel
    CMD_LINUX_LIST_JSON = "nvme list -o json"
    CMD_LINUX = {
        "smart_log": "nvme smart-log {dev}",
        "error_log": "nvme error-log {dev} --log-entries=256",
        "id_ctrl": "nvme id-ctrl {dev}",
        "id_ns": "nvme id-ns {dev}{ns}",
        "fw_log": "nvme fw-log {dev}",
        "self_test_log": "nvme self-test-log {dev}",
        "get_log": "nvme get-log {dev} --log-id=6 --log-len=512",
        "telemetry_log": "nvme telemetry-log {dev} --output-file={dev}_{f_name}",
    }
    CMD_TEMPLATES = list(CMD_LINUX.values())

    TELEMETRY_FILENAME = "telemetry_log.bin"

    def _check_nvme_cli_installed(self) -> bool:
        """Check if the nvme CLI is installed on the system.

        Returns:
            bool: True if nvme is available, False otherwise.
        """
        res = self._run_sut_cmd("which nvme")
        return res.exit_code == 0 and bool(res.stdout.strip())

    def collect_data(
        self,
        args=None,
    ) -> tuple[TaskResult, Optional[NvmeDataModel]]:
        """Collect detailed NVMe information from all NVMe devices.

        Returns:
            tuple[TaskResult, Optional[NvmeDataModel]]: Task result and data model with NVMe command outputs.
        """
        if self.system_info.os_family == OSFamily.WINDOWS:
            self._log_event(
                category=EventCategory.SW_DRIVER,
                description="NVMe collection not supported on Windows",
                priority=EventPriority.WARNING,
            )
            self.result.message = "NVMe data collection skipped on Windows"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result, None

        if not self._check_nvme_cli_installed():
            self._log_event(
                category=EventCategory.SW_DRIVER,
                description="nvme CLI not found; install nvme-cli to collect NVMe data",
                priority=EventPriority.WARNING,
            )
            self.result.message = "nvme CLI not found; NVMe collection skipped"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result, None

        nvme_list_entries = self._collect_nvme_list_entries()

        nvme_devices = self._get_nvme_devices()
        if not nvme_devices:
            self._log_event(
                category=EventCategory.SW_DRIVER,
                description="No NVMe devices found",
                priority=EventPriority.ERROR,
            )
            self.result.message = "No NVMe devices found"
            self.result.status = ExecutionStatus.ERROR
            return self.result, None

        all_device_data = {}
        f_name = self.TELEMETRY_FILENAME

        for dev in nvme_devices:
            device_data = {}
            ns_suffix = "n1"
            cmd_map = {
                k: v.format(dev=dev, ns=ns_suffix, f_name=f_name) for k, v in self.CMD_LINUX.items()
            }

            for key, cmd in cmd_map.items():
                res = self._run_sut_cmd(cmd, sudo=True)
                if "--output-file" in cmd:
                    _ = self._read_sut_file(filename=f"{dev}_{f_name}", encoding=None)

                if res.exit_code == 0:
                    device_data[key] = res.stdout
                else:
                    self._log_event(
                        category=EventCategory.SW_DRIVER,
                        description=f"Failed to execute NVMe command: '{cmd}'",
                        data={"command": cmd, "exit_code": res.exit_code},
                        priority=EventPriority.WARNING,
                        console_log=True,
                    )

            if device_data:
                all_device_data[os.path.basename(dev)] = device_data

        if all_device_data:
            try:
                nvme_data = NvmeDataModel(nvme_list=nvme_list_entries, devices=all_device_data)
            except ValidationError as exp:
                self._log_event(
                    category=EventCategory.SW_DRIVER,
                    description="Validation error while building NvmeDataModel",
                    data={"errors": exp.errors(include_url=False)},
                    priority=EventPriority.ERROR,
                )
                self.result.message = "NVMe data invalid format"
                self.result.status = ExecutionStatus.ERROR
                return self.result, None

            self._log_event(
                category=EventCategory.SW_DRIVER,
                description="Collected NVMe data",
                data={
                    "devices": list(nvme_data.devices.keys()),
                    "nvme_list_entries": len(nvme_data.nvme_list or []),
                },
                priority=EventPriority.INFO,
            )
            self.result.message = "NVMe data successfully collected"
            self.result.status = ExecutionStatus.OK
            return self.result, nvme_data
        else:

            self._log_event(
                category=EventCategory.SW_DRIVER,
                description="Failed to collect any NVMe data",
                priority=EventPriority.ERROR,
            )
            self.result.message = "No NVMe data collected"
            self.result.status = ExecutionStatus.ERROR
            return self.result, None

    def _collect_nvme_list_entries(self) -> Optional[list[NvmeListEntry]]:
        """Run 'nvme list -o json' and parse output into list of NvmeListEntry."""
        res = self._run_sut_cmd(self.CMD_LINUX_LIST_JSON, sudo=False)
        if res.exit_code == 0 and res.stdout:
            entries = self._parse_nvme_list_json(res.stdout.strip())
            if not entries:
                self._log_event(
                    category=EventCategory.SW_DRIVER,
                    description="Parsing of 'nvme list -o json' output failed (no entries from nested or flat format)",
                    priority=EventPriority.WARNING,
                )
            return entries
        return None

    def _parse_nvme_list_json(self, raw: str) -> list[NvmeListEntry]:
        """Parse 'nvme list -o json' output into NvmeListEntry list.

        Supports two formats:
        - Nested: Devices[] -> Subsystems[] -> Controllers[] -> Namespaces[].
        - Flat: Devices[] where each element has DevicePath, SerialNumber, ModelNumber, etc.
        """
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        devices = data.get("Devices", []) if isinstance(data, dict) else []
        if not isinstance(devices, list):
            return []
        entries = self._parse_nvme_list_nested(devices)
        if not entries and devices:
            entries = self._parse_nvme_list_flat(devices)
        return entries

    def _parse_nvme_list_flat(self, devices: list) -> list[NvmeListEntry]:
        """Parse flat 'nvme list -o json' format (one object per namespace in Devices[])."""
        entries = []
        for dev in devices:
            if not isinstance(dev, dict):
                continue
            if dev.get("DevicePath") is None and dev.get("SerialNumber") is None:
                continue
            node = str_or_none(dev.get("DevicePath"))
            generic_path = str_or_none(dev.get("GenericPath"))
            serial_number = str_or_none(dev.get("SerialNumber"))
            model = str_or_none(dev.get("ModelNumber"))
            fw_rev = str_or_none(dev.get("Firmware"))
            name_space = dev.get("NameSpace") or dev.get("NameSpaceId")
            nsid = name_space if name_space is not None else dev.get("NSID")
            namespace_id = (
                f"0x{int(nsid):x}" if isinstance(nsid, (int, float)) else str_or_none(nsid)
            )
            used_bytes = dev.get("UsedBytes")
            physical_size = dev.get("PhysicalSize")
            sector_size = dev.get("SectorSize")
            if isinstance(used_bytes, (int, float)) and isinstance(physical_size, (int, float)):
                usage = (
                    f"{bytes_to_human_readable(int(used_bytes))} / "
                    f"{bytes_to_human_readable(int(physical_size))}"
                )
            else:
                usage = None
            format_lba = f"{sector_size}   B +  0 B" if sector_size is not None else None
            entries.append(
                NvmeListEntry(
                    node=node,
                    generic=generic_path,
                    serial_number=serial_number,
                    model=model,
                    namespace_id=namespace_id,
                    usage=usage,
                    format_lba=format_lba,
                    fw_rev=fw_rev,
                )
            )
        return entries

    def _parse_nvme_list_nested(self, devices: list) -> list[NvmeListEntry]:
        """Parse nested 'nvme list -o json' format (Devices -> Subsystems -> Controllers -> Namespaces)."""
        entries = []
        for dev in devices:
            if not isinstance(dev, dict):
                continue
            subsystems = dev.get("Subsystems") or []
            for subsys in subsystems:
                if not isinstance(subsys, dict):
                    continue
                controllers = subsys.get("Controllers") or []
                for ctrl in controllers:
                    if not isinstance(ctrl, dict):
                        continue
                    serial_number = str_or_none(ctrl.get("SerialNumber"))
                    model = str_or_none(ctrl.get("ModelNumber"))
                    fw_rev = str_or_none(ctrl.get("Firmware"))
                    namespaces = ctrl.get("Namespaces") or []
                    for ns in namespaces:
                        if not isinstance(ns, dict):
                            continue
                        name_space = ns.get("NameSpace") or ns.get("NameSpaceId")
                        generic = ns.get("Generic")
                        nsid = ns.get("NSID")
                        used_bytes = ns.get("UsedBytes")
                        physical_size = ns.get("PhysicalSize")
                        sector_size = ns.get("SectorSize")
                        node = f"/dev/{name_space}" if name_space else None
                        generic_path = (
                            f"/dev/{generic}" if (generic and str(generic).strip()) else None
                        )
                        namespace_id = f"0x{nsid:x}" if isinstance(nsid, int) else str_or_none(nsid)
                        if isinstance(used_bytes, (int, float)) and isinstance(
                            physical_size, (int, float)
                        ):
                            usage = (
                                f"{bytes_to_human_readable(int(used_bytes))} / "
                                f"{bytes_to_human_readable(int(physical_size))}"
                            )
                        else:
                            usage = None
                        format_lba = (
                            f"{sector_size}   B +  0 B" if sector_size is not None else None
                        )
                        entries.append(
                            NvmeListEntry(
                                node=str_or_none(node),
                                generic=str_or_none(generic_path),
                                serial_number=serial_number,
                                model=model,
                                namespace_id=namespace_id,
                                usage=usage,
                                format_lba=format_lba,
                                fw_rev=fw_rev,
                            )
                        )
        return entries

    def _get_nvme_devices(self) -> list[str]:
        nvme_devs = []

        res = self._run_sut_cmd("ls /dev", sudo=False)
        if res.exit_code != 0:
            self._log_event(
                category=EventCategory.SW_DRIVER,
                description="Failed to list /dev directory",
                data={"exit_code": res.exit_code, "stderr": res.stderr},
                priority=EventPriority.ERROR,
            )
            return []

        for entry in res.stdout.strip().splitlines():
            if re.fullmatch(r"nvme\d+$", entry):
                nvme_devs.append(f"/dev/{entry}")

        return nvme_devs
