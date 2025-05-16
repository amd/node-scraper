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

from errorscraper.base import InBandDataCollector
from errorscraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from errorscraper.models import TaskResult

from .uptimedata import UptimeDataModel


class UptimeCollector(InBandDataCollector[UptimeDataModel, None]):
    """Collect last boot time and uptime from uptime command"""

    DATA_MODEL = UptimeDataModel

    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.LINUX}

    UPTIME_CMD = "uptime"

    def collect_data(self, args=None) -> tuple[TaskResult, UptimeDataModel | None]:
        """Read uptime data"""

        uptime_pattern = re.compile(
            r"(?P<current_time>\d{2}:\d{2}:\d{2})\s+" r"up\s+(?P<uptime>.+?),\s+\d+\s+users?"
        )

        res = self._run_sut_cmd(self.UPTIME_CMD)

        if res.exit_code == 0:
            line = res.stdout.strip()
            match = uptime_pattern.match(line)

            if match:
                current_time = match.group("current_time")
                uptime = match.group("uptime")

        else:
            self._log_event(
                category=EventCategory.OS,
                description="Error running uptime command",
                data={"command": res.command, "exit_code": res.exit_code},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.message = "Failed to run uptime command"
            self.result.status = ExecutionStatus.EXECUTION_FAILURE
            return self.result, None

        uptime_data = UptimeDataModel(current_time=current_time, uptime=uptime)

        self._log_event(
            category=EventCategory.OS,
            description="Uptime data collected",
            data=uptime_data.model_dump(),
            priority=EventPriority.INFO,
        )
        self.result.message = f"Uptime: {uptime}"
        self.result.status = ExecutionStatus.OK
        return self.result, uptime_data
