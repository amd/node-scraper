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
###########################

from errorscraper.event import EventCategory, EventPriority

from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult, TaskStatus
from nodescraper.plugins.inband.deviceenumdata import DeviceEnumerationDataModel


class DeviceEnumerationAnalyzer(
    DataAnalyzer[DeviceEnumerationDataModel, DeviceEnumerationAnalyzerArgs]
):
    """Check Device Enumeration matches expected cpu and gpu count
    supported by all OSs, SKUs, and platforms."""

    DATA_MODEL = DeviceEnumerationDataModel

    def analyze_data(
        self, data: DeviceEnumerationDataModel, args: Optional[DeviceEnumerationAnalyzerArgs] = None
    ) -> TaskResult:

        if not args:
            self.result.message = "Expected Device Enumeration expected data not provided"
            self.result.status = TaskStatus.NOT_RAN
            return self.result

        if isinstance(args.cpu_count, int):
            cpu_count = [args.cpu_count]
        if isinstance(args.gpu_count, int):
            gpu_count = [args.gpu_count]
        if isinstance(args.vf_count, int):
            vf_count = [args.vf_count]

        checks = {}
        if cpu_count not in [None, []]:
            checks["cpu_count"] = cpu_count
        if gpu_count not in [None, []]:
            checks["gpu_count"] = gpu_count
        if vf_count not in [None, []]:
            checks["vf_count"] = vf_count

        self.result.message = ""
        for check, accepted_counts in checks.items():
            actual_count = getattr(data, check)
            if actual_count not in accepted_counts:
                message = f"Expected {check} in {accepted_counts}, but got {actual_count}. "
                self.result.message += message
                self.result.status = TaskStatus.ERRORS_DETECTED
                self._log_event(
                    category=EventCategory.PLATFORM,
                    description=message,
                    data={check: actual_count},
                    priority=EventPriority.CRITICAL,
                    console_log=True,
                )
        if self.result.message == "":
            self.result.status = TaskStatus.OK
            self.result.message = f"Device Enumeration validated on {checks.keys()}."

        return self.result
