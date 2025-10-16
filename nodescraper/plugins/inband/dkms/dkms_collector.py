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
from nodescraper.base import InBandDataCollector
from nodescraper.enums import EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult

from .dkmsdata import DkmsDataModel


class DkmsCollector(InBandDataCollector[DkmsDataModel, None]):
    """Collect DKMS status and version data"""

    SUPPORTED_OS_FAMILY = {OSFamily.LINUX}

    DATA_MODEL = DkmsDataModel

    CMD_STATUS = "dkms status"
    CMD_VERSION = "dkms --version"

    def collect_data(
        self,
        args=None,
    ) -> tuple[TaskResult, DkmsDataModel | None]:
        """
        Collect DKMS status and version information.

        Returns:
            tuple[TaskResult, DkmsDataModel | None]: tuple containing the task result and DKMS data model if available.
        """

        dkms_data = DkmsDataModel()
        dkms_status = self._run_sut_cmd(self.CMD_STATUS)
        dkms_version = self._run_sut_cmd(self.CMD_VERSION)

        if dkms_status.exit_code == 0:
            dkms_data.status = dkms_status.stdout

        if dkms_version.exit_code == 0:
            dkms_data.version = dkms_version.stdout

        dkms = bool(dkms_data.model_fields_set)
        if dkms:
            self._log_event(
                category="DKMS_READ",
                description="DKMS data read",
                data=dkms_data.model_dump(),
                priority=EventPriority.INFO,
            )
        self.result.message = f"DKMS: {dkms_data.model_dump()}" if dkms else "DKMS info not found"
        self.result.status = ExecutionStatus.OK if dkms else ExecutionStatus.ERROR
        return self.result, dkms_data if dkms else None
