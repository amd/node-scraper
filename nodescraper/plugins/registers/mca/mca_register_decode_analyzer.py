###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
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
from nodescraper.enums import (
    EventCategory,
    EventPriority,
    ExecutionStatus,
    SystemLocation,
)
from nodescraper.models import TaskResult
from nodescraper.plugins.registers.register_decode_analyzer import (
    RegisterDecodeAnalyzer,
)
from nodescraper.plugins.registers.register_decode_data import RegisterDecodeDataModel

from .mca_register_decode_data import McaRegisterDecodeDataModel


class McaRegisterDecodeAnalyzer(RegisterDecodeAnalyzer):
    """Report MCA register records already decoded on the data model."""

    DATA_MODEL = McaRegisterDecodeDataModel

    def analyze_data(self, data: RegisterDecodeDataModel, args: None = None) -> TaskResult:
        """Report decoded MCA register and dmesg records.

        Args:
            data: Collected stats, MCA records, and decoded results.
            args: Analysis arguments. Defaults to None.

        Returns:
            Task result for the decoded records.
        """
        if not isinstance(data, McaRegisterDecodeDataModel):
            return super().analyze_data(data, args)
        if data.decoded_records is not None or data.dmesg_decoded_records is not None:
            return self._report_mca(data)
        if self.system_info.location == SystemLocation.REMOTE:
            message = "MCA register decode is only supported on local"
            self.result.status = ExecutionStatus.NOT_RAN
            self.result.message = message
            self._log_event(
                category=EventCategory.RAS,
                description=message,
                priority=EventPriority.INFO,
                console_log=True,
            )
            return self.result
        return self._fail("MCA register records were not decoded during collection")

    def _report_mca(self, data: McaRegisterDecodeDataModel) -> TaskResult:
        """Report MCA records already decoded on the data model.

        Args:
            data: Collected records plus decoded MSR and dmesg results.

        Returns:
            Task result for the decode.
        """
        decoded = list(data.decoded_records or [])
        dmesg_decoded = list(data.dmesg_decoded_records or [])
        self.result.status = ExecutionStatus.OK
        self.result.message = f"Decoded {len(decoded)} MCA register record(s) and {len(dmesg_decoded)} dmesg record(s)"
        self._log_event(
            category=EventCategory.RAS,
            description=self.result.message,
            data={"records": decoded, "dmesg_records": dmesg_decoded},
            priority=EventPriority.INFO,
        )
        return self.result
