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
from typing import Optional

from nodescraper.base import InBandDataCollector
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult

from .biosdata import BiosDataModel


class BiosCollector(InBandDataCollector[BiosDataModel, None]):
    """Collect BIOS details"""

    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.WINDOWS, OSFamily.LINUX, OSFamily.ESXI}
    DATA_MODEL = BiosDataModel
    CMD_WINDOWS = "wmic bios get SMBIOSBIOSVersion /Value"
    CMD_SYSTEM_WINDOWS = "wmic computersystem get Manufacturer,Model /Value"
    CMD = "sh -c 'cat /sys/devices/virtual/dmi/id/bios_version'"
    CMD_SYS_VENDOR = "sh -c 'cat /sys/devices/virtual/dmi/id/sys_vendor'"
    CMD_PRODUCT_NAME = "sh -c 'cat /sys/devices/virtual/dmi/id/product_name'"
    CMD_ESXI = "smbiosDump | grep -A5 'BIOS Info (Type 0)' | grep 'Version:' | head -1"
    CMD_ESXI_SYSTEM = "smbiosDump | grep -A20 'System Info (Type 1)'"

    def collect_data(
        self,
        args=None,
    ) -> tuple[TaskResult, Optional[BiosDataModel]]:
        """Collect BIOS version information from the system.

        Returns:
            tuple[TaskResult, Optional[BiosDataModel]]: tuple containing the task result and an instance of BiosDataModel
            or None if the BIOS version could not be determined.
        """
        bios = None
        server_vendor = None
        server_model = None

        if self.system_info.os_family == OSFamily.WINDOWS:
            res = self._run_sut_cmd(self.CMD_WINDOWS)
            if res.exit_code == 0:
                bios = [line for line in res.stdout.splitlines() if "SMBIOSBIOSVersion=" in line][
                    0
                ].split("=")[1]
        elif self.system_info.os_family == OSFamily.ESXI:
            res = self._run_sut_cmd(self.CMD_ESXI)
            if res.exit_code == 0:
                match = re.search(r'Version:\s*"?([^"]+)"?', res.stdout)
                bios = match.group(1).strip() if match else res.stdout.strip()
        else:
            res = self._run_sut_cmd(self.CMD)
            if res.exit_code == 0:
                bios = res.stdout

        if res.exit_code != 0:
            self._log_event(
                category=EventCategory.OS,
                description="Error checking BIOS version",
                data={"command": res.command, "exit_code": res.exit_code},
                priority=EventPriority.ERROR,
                console_log=True,
            )

        if bios:
            server_vendor, server_model = self._collect_server_identity()
            bios_data = BiosDataModel(
                bios_version=bios,
                server_vendor=server_vendor,
                server_model=server_model,
            )
            self._log_event(
                category="BIOS_READ",
                description="BIOS version read",
                data=bios_data.model_dump(),
                priority=EventPriority.INFO,
            )
            self.result.message = f"BIOS: {bios}"
        else:
            bios_data = None
            self._log_event(
                category=EventCategory.BIOS,
                description="BIOS version not found",
                priority=EventPriority.CRITICAL,
            )
            self.result.message = "BIOS version not found"
            self.result.status = ExecutionStatus.ERROR

        return self.result, bios_data

    def _collect_server_identity(self) -> tuple[Optional[str], Optional[str]]:
        """Read the server vendor and model. These are the platform, not the GPU."""
        if self.system_info.os_family == OSFamily.WINDOWS:
            res = self._run_sut_cmd(self.CMD_SYSTEM_WINDOWS)
            if res.exit_code != 0:
                self._log_identity_warning(res, "server vendor and model")
                return None, None
            vendor = self._labeled_value(res.stdout, "Manufacturer")
            model = self._labeled_value(res.stdout, "Model")
            return vendor, model

        if self.system_info.os_family == OSFamily.ESXI:
            res = self._run_sut_cmd(self.CMD_ESXI_SYSTEM)
            if res.exit_code != 0:
                self._log_identity_warning(res, "server vendor and model")
                return None, None
            return self._parse_esxi_system(res.stdout)

        vendor = self._read_sysfs_value(self.CMD_SYS_VENDOR, "server vendor")
        model = self._read_sysfs_value(self.CMD_PRODUCT_NAME, "server model")
        return vendor, model

    def _read_sysfs_value(self, command: str, label: str) -> Optional[str]:
        res = self._run_sut_cmd(command)
        if res.exit_code != 0:
            self._log_identity_warning(res, label)
            return None
        text = (res.stdout or "").strip()
        return text or None

    def _log_identity_warning(self, res, label: str) -> None:
        self._log_event(
            category=EventCategory.OS,
            description=f"Error checking {label}",
            data={"command": res.command, "exit_code": res.exit_code},
            priority=EventPriority.WARNING,
            console_log=True,
        )

    @staticmethod
    def _labeled_value(stdout: str, key: str) -> Optional[str]:
        prefix = f"{key}="
        for line in stdout.splitlines():
            if line.startswith(prefix):
                value = line.split("=", 1)[1].strip()
                return value or None
        return None

    @staticmethod
    def _parse_esxi_system(stdout: str) -> tuple[Optional[str], Optional[str]]:
        vendor = None
        model = None
        in_system = False
        for line in stdout.splitlines():
            if "System Info" in line and "Type 1" in line:
                in_system = True
                continue
            if not in_system:
                continue
            stripped = line.strip()
            if stripped.startswith("System Info") or re.match(r".*Info \(Type \d+\)", stripped):
                break
            if stripped.lower().startswith("manufacturer:"):
                vendor = BiosCollector._unquote_smbios(stripped.split(":", 1)[1])
            elif stripped.lower().startswith("product:"):
                model = BiosCollector._unquote_smbios(stripped.split(":", 1)[1])
        return vendor, model

    @staticmethod
    def _unquote_smbios(value: str) -> Optional[str]:
        text = value.strip()
        if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
            text = text[1:-1].strip()
        return text or None
