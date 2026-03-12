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
from typing import Optional

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .analyzer_args import RedfishOemDiagAnalyzerArgs
from .oem_diag_data import RedfishOemDiagDataModel


class RedfishOemDiagAnalyzer(DataAnalyzer[RedfishOemDiagDataModel, RedfishOemDiagAnalyzerArgs]):
    """Analyzes Redfish OEM diagnostic log collection results."""

    DATA_MODEL = RedfishOemDiagDataModel

    def analyze_data(
        self,
        data: RedfishOemDiagDataModel,
        args: Optional[RedfishOemDiagAnalyzerArgs] = None,
    ) -> TaskResult:
        """Check collection results; optionally fail if any type failed."""
        if not data.results:
            self.result.message = "No OEM diagnostic results to analyze"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result

        failed = [t for t, r in data.results.items() if not r.success]
        success_count = len(data.results) - len(failed)

        if args and args.require_all_success and failed:
            self._log_event(
                category=EventCategory.RUNTIME,
                description=f"OEM diag types failed: {failed}",
                data={t: data.results[t].error for t in failed},
                priority=EventPriority.ERROR,
                console_log=True,
            )
            self.result.message = f"OEM diag: {len(failed)} type(s) failed: {failed}"
            self.result.status = ExecutionStatus.ERROR
            return self.result

        self.result.message = f"OEM diag: {success_count}/{len(data.results)} types collected"
        self.result.status = ExecutionStatus.OK
        return self.result
