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

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .analyzer_args import OsAnalyzerArgs
from .osdata import OsDataModel


class OsAnalyzer(DataAnalyzer[OsDataModel, OsAnalyzerArgs]):
    """Check os matches expected versions"""

    DATA_MODEL = OsDataModel

    def analyze_data(self, data: OsDataModel, args: Optional[OsAnalyzerArgs] = None) -> TaskResult:
        """Analyze the OS data against expected OS names.

        Args:
            data (OsDataModel): Operating System data to analyze.
            args (Optional[OsAnalyzerArgs], optional): OS analysis arguments. Defaults to None.

        Returns:
            TaskResult: Result of the analysis containing status and message.
        """
        if args is None:
            args = OsAnalyzerArgs()

        if not args.exp_os and args.maximum_load_per_cpu_core is None:
            self.result.message = "Expected OS name not provided"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result

        os_name_matches = True
        load_check_warning = False
        load_check_error = False

        if args.exp_os:
            os_name_matches = False
            for os_name in args.exp_os:
                if (os_name == data.os_name and args.exact_match) or (
                    os_name in data.os_name and not args.exact_match
                ):
                    os_name_matches = True
                    break

            if not os_name_matches:
                self._log_event(
                    category=EventCategory.OS,
                    description=f"OS name mismatch! Expected: {args.exp_os}, actual: {data.os_name}",
                    data={"expected": args.exp_os, "actual": data.os_name},
                    priority=EventPriority.CRITICAL,
                    console_log=True,
                )

        if args.maximum_load_per_cpu_core is not None:
            if data.load_average_1m is None or data.cpu_count is None or data.cpu_count <= 0:
                load_check_warning = True
                self._log_event(
                    category=EventCategory.OS,
                    description="Cannot validate maximum load per CPU core",
                    data={
                        "load_average_1m": data.load_average_1m,
                        "cpu_count": data.cpu_count,
                    },
                    priority=EventPriority.WARNING,
                    console_log=True,
                )
            else:
                load_per_cpu_core = data.load_average_1m / data.cpu_count
                if load_per_cpu_core > args.maximum_load_per_cpu_core:
                    load_check_error = True
                    self._log_event(
                        category=EventCategory.OS,
                        description=(
                            f"Load per CPU core is {load_per_cpu_core:.2f} "
                            f"(maximum {args.maximum_load_per_cpu_core:.2f})"
                        ),
                        data={
                            "load_average_1m": data.load_average_1m,
                            "cpu_count": data.cpu_count,
                            "load_per_cpu_core": load_per_cpu_core,
                            "maximum_load_per_cpu_core": args.maximum_load_per_cpu_core,
                        },
                        priority=EventPriority.CRITICAL,
                        console_log=True,
                    )

        if not os_name_matches:
            self.result.message = "OS name mismatch!"
            self.result.status = ExecutionStatus.ERROR
        elif load_check_error:
            self.result.message = "Maximum load per CPU core exceeded"
            self.result.status = ExecutionStatus.ERROR
        elif load_check_warning:
            self.result.message = "CPU load data is not available"
            self.result.status = ExecutionStatus.WARNING
        else:
            self.result.message = (
                "OS name matches expected" if args.exp_os else "Load per CPU core is within limit"
            )
            self.result.status = ExecutionStatus.OK
        return self.result
