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
from errorscraper.base import InBandDataCollector
from errorscraper.enums import EventCategory, EventPriority, OSFamily
from errorscraper.models import TaskResult

from .dmesgdata import DmesgData


class DmesgCollector(InBandDataCollector[DmesgData, None]):
    """Read dmesg log"""

    SUPPORTED_OS_FAMILY = {OSFamily.LINUX}

    DATA_MODEL = DmesgData

    DMESG_CMD = "dmesg --time-format iso -x"

    def _get_dmesg_content(self) -> str:
        """run dmesg command on system and return output

        Returns:
            str: dmesg output
        """

        self.logger.info("Running dmesg command on system")
        res = self._run_sut_cmd(self.DMESG_CMD, sudo=True, log_artifact=False)
        if res.exit_code != 0:
            self._log_event(
                category=EventCategory.OS,
                description="Error reading dmesg",
                data={"command": res.command, "exit_code": res.exit_code},
                priority=EventPriority.ERROR,
                console_log=True,
            )
        return res.stdout

    def collect_data(
        self,
        args=None,
    ) -> tuple[TaskResult, DmesgData | None]:
        dmesg_content = self._get_dmesg_content()

        if dmesg_content:
            dmesg_data = DmesgData(dmesg_content=dmesg_content)
            self.result.message = "Dmesg data collected"
            return self.result, dmesg_data

        return self.result, None
