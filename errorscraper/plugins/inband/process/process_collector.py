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

from errorscraper.base import InBandDataCollector
from errorscraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from errorscraper.models import TaskResult

from .collector_args import ProcessCollectorArgs
from .processdata import ProcessDataModel


class ProcessCollector(InBandDataCollector[ProcessDataModel, ProcessCollectorArgs]):
    """Collect Process details"""

    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.LINUX}

    DATA_MODEL = ProcessDataModel

    def collect_data(
        self, args: Optional[ProcessCollectorArgs] = None
    ) -> tuple[TaskResult, ProcessDataModel | None]:
        """Collect process data from the system.

        Args:
            args (Optional[ProcessCollectorArgs], optional): process collection arguments. Defaults to None.

        Returns:
            tuple[TaskResult, ProcessDataModel | None]: tuple containing the task result and the collected process data model or None if no data was collected.
        """
        if args is None:
            args = ProcessCollectorArgs()

        process_data = ProcessDataModel()
        process_data.processes = []

        kfd_process = self._run_sut_cmd("rocm-smi --showpids")
        if kfd_process.exit_code == 0:
            if "No KFD PIDs currently running" in kfd_process.stdout:
                process_data.kfd_process = 0
            else:
                kfd_process = re.findall(
                    r"^\s*\d+\s+[\w]+\s+\d+\s+\d+\s+\d+\s+\d+",
                    kfd_process.stdout,
                    re.MULTILINE,
                )
                process_data.kfd_process = len(kfd_process)

        cpu_usage = self._run_sut_cmd("top -b -n 1")
        if cpu_usage.exit_code == 0:
            cpu_idle = (
                [line for line in cpu_usage.stdout.splitlines() if "Cpu(s)" in line][0]
                .split(",")[3]
                .split()[0]
                .replace("%id", "")
            )
            process_data.cpu_usage = 100 - float(cpu_idle)

        processes = self._run_sut_cmd(
            f"top -b -n 1 -o %CPU | sed -n '8,{args.top_n_process + 7}p'"
        )  # Remove system header
        if processes.exit_code == 0:
            for line in processes.stdout.splitlines():
                columns = line.split()
                process_cpu_usage = columns[8]
                process_name = columns[11]
                process_data.processes.append((process_name, process_cpu_usage))

        process_check = bool(process_data.model_fields_set)
        if process_check:
            self._log_event(
                category="PROCESS_READ",
                description="Process data collected",
                data=process_data.model_dump(),
                priority=EventPriority.INFO,
            )
            self.result.message = "Process data collected"
            self.result.status = ExecutionStatus.OK
            return self.result, process_data
        else:
            self._log_event(
                category=EventCategory.OS,
                description="Process data not found",
                priority=EventPriority.ERROR,
            )
            self.result.message = "Process data not found"
            self.result.status = ExecutionStatus.ERROR
            return self.result, None
