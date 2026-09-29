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
from nodescraper.connection.inband import TextFileArtifact
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult

from .collector_args import DimmCollectorArgs
from .dimmdata import DimmDataModel


class DimmCollector(InBandDataCollector[DimmDataModel, DimmCollectorArgs]):
    """Collect data on installed DIMMs"""

    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.WINDOWS, OSFamily.LINUX, OSFamily.ESXI}
    DATA_MODEL = DimmDataModel

    CMD_WINDOWS = "wmic memorychip get Capacity"
    CMD = """sh -c 'dmidecode -t 17 | tr -s " " | grep -v "Volatile\\|None\\|Module" | grep Size' 2>/dev/null"""
    CMD_ESXI = "smbiosDump | grep -A15 'Memory Device (Type 17)' | grep 'Size:'"
    CMD_DMIDECODE_FULL = "dmidecode"

    def _parse_dmi_sizes(self, stdout: str) -> str:
        """Build the DIMM summary from 'Size: <n> <unit>' lines (dmidecode on Linux,
        smbiosDump on ESXi — both emit the same field format)."""
        total = 0
        topology: dict[str, int] = {}
        size = ""
        dimm_size_pattern = re.compile(r"Size:\s+(\d+)\s+([A-Za-z]+)")
        for num, unit in dimm_size_pattern.findall(stdout):
            size = unit
            total += int(num)
            key = num + unit
            topology[key] = topology.get(key, 0) + 1
        if total == 0:
            return "0 GB"
        dimm_entries = [f"{v} x {k}" for k, v in topology.items()]
        return f"{total}{size} @ {' '.join(dimm_entries)}"

    def collect_data(
        self,
        args: Optional[DimmCollectorArgs] = None,
    ) -> tuple[TaskResult, Optional[DimmDataModel]]:
        """Collect data on installed DIMMs"""
        if args is None:
            args = DimmCollectorArgs()

        dimm_str = None
        if self.system_info.os_family == OSFamily.WINDOWS:
            res = self._run_sut_cmd(self.CMD_WINDOWS)
            if res.exit_code == 0:
                capacities = {}
                total = 0
                for line in res.stdout.splitlines():
                    value = line.strip()
                    if value.isdigit():
                        value = int(value)
                        total += value
                        if value not in capacities:
                            capacities[value] = 1
                        else:
                            capacities[value] += 1
                dimm_str = f"{total / 1024 / 1024:.2f}GB @ "
                for capacity, count in capacities.items():
                    dimm_str += f"{count} x {capacity / 1024 / 1024:.2f}GB "
        elif self.system_info.os_family == OSFamily.ESXI:
            res = self._run_sut_cmd(self.CMD_ESXI)
            if res.exit_code == 0:
                dimm_str = self._parse_dmi_sizes(res.stdout)
        else:
            if args.skip_sudo:
                self.result.message = "Skipping sudo plugin"
                self.result.status = ExecutionStatus.NOT_RAN
                return self.result, None

            # Collect full dmidecode output as artifact
            dmidecode_full_res = self._run_sut_cmd(self.CMD_DMIDECODE_FULL, sudo=True)
            if dmidecode_full_res.exit_code == 0 and dmidecode_full_res.stdout:
                self.result.artifacts.append(
                    TextFileArtifact(filename="dmidecode.txt", contents=dmidecode_full_res.stdout)
                )
            else:
                self._log_event(
                    category=EventCategory.OS,
                    description="Could not collect full dmidecode output",
                    data={
                        "command": dmidecode_full_res.command,
                        "exit_code": dmidecode_full_res.exit_code,
                        "stderr": dmidecode_full_res.stderr,
                    },
                    priority=EventPriority.WARNING,
                )

            res = self._run_sut_cmd(self.CMD, sudo=True)
            if res.exit_code == 0:
                dimm_str = self._parse_dmi_sizes(res.stdout)
        if res.exit_code != 0:
            self._log_event(
                category=EventCategory.OS,
                description="Error checking dimms",
                data={
                    "command": res.command,
                    "exit_code": res.exit_code,
                    "stderr": res.stderr,
                },
                priority=EventPriority.ERROR,
                console_log=True,
            )

        if dimm_str:
            dimm_data = DimmDataModel(dimms=dimm_str)
            self._log_event(
                category=EventCategory.IO,
                description="Installed DIMM check",
                data=dimm_data.model_dump(),
                priority=EventPriority.INFO,
            )
            self.result.message = f"DIMM: {dimm_str}"
        else:
            dimm_data = None
            self._log_event(
                category=EventCategory.IO,
                description="DIMM info not found",
                priority=EventPriority.CRITICAL,
            )
            self.result.message = "DIMM info not found"
            self.result.status = ExecutionStatus.ERROR

        return self.result, dimm_data
