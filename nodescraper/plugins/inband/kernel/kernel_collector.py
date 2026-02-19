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

from .kerneldata import KernelDataModel


class KernelCollector(InBandDataCollector[KernelDataModel, None]):
    """Read kernel version"""

    DATA_MODEL = KernelDataModel
    CMD_WINDOWS = "wmic os get Version /Value"
    CMD = "sh -c 'uname -a'"
    CMD_NUMA_BALANCING = "sh -c 'cat /proc/sys/kernel/numa_balancing'"

    def _parse_kernel_version(self, uname_a: str) -> Optional[str]:
        """Extract the kernel release from `uname -a` output.

        Args:
            uname_a (str): The full output string from the `uname -a` command.

        Returns:
            Optional[str]: The parsed kernel release (e.g., "5.13.0-30-generic")
            if found, otherwise None.
        """
        if not uname_a:
            return None

        result = uname_a.strip().split()
        if len(result) >= 3:
            return result[2]

        # if some change in output look for a version-like string (e.g. 4.18.0-553.el8_10.x86_64)
        match = re.search(r"\d+\.\d+\.\d+[\w\-\.]*", uname_a)
        if match:
            return match.group(0)

        return None

    def collect_data(
        self,
        args=None,
    ) -> tuple[TaskResult, Optional[KernelDataModel]]:
        """
        Collect kernel version data.

        Returns:
            tuple[TaskResult, Optional[KernelDataModel]]: tuple containing the task result and kernel data model or None if not found.
        """

        kernel = None
        kernel_info = None
        numa_balancing = None

        if self.system_info.os_family == OSFamily.WINDOWS:
            res = self._run_sut_cmd(self.CMD_WINDOWS)
            if res.exit_code == 0:
                kernel_info = res.stdout
                kernel = [line for line in res.stdout.splitlines() if "Version=" in line][0].split(
                    "="
                )[1]
        else:
            res = self._run_sut_cmd(self.CMD)
            if res.exit_code == 0:
                kernel_info = res.stdout
                kernel = self._parse_kernel_version(kernel_info)
                numa_res = self._run_sut_cmd(self.CMD_NUMA_BALANCING)
                if numa_res.exit_code == 0 and numa_res.stdout.strip().isdigit():
                    numa_balancing = int(numa_res.stdout.strip())
                if not kernel:
                    self._log_event(
                        category=EventCategory.OS,
                        description="Could not extract kernel version from 'uname -a'",
                        data={"command": res.command, "exit_code": res.exit_code},
                        priority=EventPriority.ERROR,
                        console_log=True,
                    )

        if res.exit_code != 0:
            self._log_event(
                category=EventCategory.OS,
                description="Error checking kernel version",
                data={"command": res.command, "exit_code": res.exit_code},
                priority=EventPriority.ERROR,
                console_log=True,
            )

        if kernel_info and kernel:

            kernel_data = KernelDataModel(
                kernel_info=kernel_info,
                kernel_version=kernel,
                numa_balancing=numa_balancing,
            )
            self._log_event(
                category="KERNEL_READ",
                description="Kernel version read",
                data=kernel_data.model_dump(),
                priority=EventPriority.INFO,
            )
        else:
            kernel_data = None

        self.result.message = (
            "Kernel not found"
            if not kernel_info
            else f"Kernel info: {kernel_info} | Kernel version: {kernel if kernel else 'Kernel version not found'}"
        )
        self.result.status = ExecutionStatus.OK if kernel_info else ExecutionStatus.ERROR
        return self.result, kernel_data
