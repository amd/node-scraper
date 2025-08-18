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
from typing import Optional

from nodescraper.base import InBandDataCollector
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult

from .collector_args import DimmCollectorArgs
from .dimmdata import DimmDataModel


class DimmCollector(InBandDataCollector[DimmDataModel, DimmCollectorArgs]):
    """Collect data on installed DIMMs"""

    DATA_MODEL = DimmDataModel

    def collect_data(
        self,
        args: Optional[DimmCollectorArgs] = None,
    ) -> tuple[TaskResult, DimmDataModel | None]:
        """Collect data on installed DIMMs"""
        if args is None:
            args = DimmCollectorArgs()

        dimm_str = None
        if self.system_info.os_family == OSFamily.WINDOWS:
            res = self._run_sut_cmd("wmic memorychip get Capacity")
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
        else:
            if args.skip_sudo:
                self.result.message = "Skipping sudo plugin"
                self.result.status = ExecutionStatus.NOT_RAN
                return self.result, None
            res = self._run_sut_cmd(
                """sh -c 'dmidecode -t 17 | tr -s " " | grep -v "Volatile\\|None\\|Module" | grep Size' 2>/dev/null""",
                sudo=True,
            )
            if res.exit_code == 0:
                total = 0
                topology = {}
                size = None
                for d in res.stdout.splitlines():
                    split = d.split()
                    size = split[2]
                    key = split[1] + split[2]
                    if not topology.get(key, None):
                        topology[key] = 1
                    else:
                        topology[key] += 1
                    num_gb = int(split[1])
                    total += num_gb
                topology["total"] = total
                topology["size"] = size
                total_gb = topology.pop("total")
                size = topology.pop("size")
                dimm_str = str(total_gb) + size + " @"
                for size, count in topology.items():
                    dimm_str += f" {count} x {size}"

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
