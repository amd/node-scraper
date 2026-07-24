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
from __future__ import annotations

from typing import Optional

from nodescraper.enums import ExecutionStatus
from nodescraper.interfaces import DataAnalyzer
from nodescraper.models import TaskResult

from .analysis_window import analyze_serviceability_window
from .analyzer_args import ServiceabilityAnalyzerArgs
from .se_adapter import format_serviceability_solution_lines
from .se_models import ServiceabilityBlock
from .serviceability_data import ServiceabilityDataModel


class ServiceabilityHubAnalyzer(
    DataAnalyzer[ServiceabilityDataModel, ServiceabilityAnalyzerArgs],
):
    """Build AFID events from collected data and run the configured service hub."""

    DATA_MODEL = ServiceabilityDataModel

    DOCUMENTATION_ANALYSIS_ITEMS: tuple[str, ...] = (
        "Builds AFID events from collected Redfish event log members (and optional assembly metadata).",
        "Optionally decodes CPER attachments via analysis_args.cper_decode_module before hub analysis.",
        "Runs the configured service hub (hub_python_module or hub_entry_point) to produce service recommendations.",
        "When analysis_args.skip_hub is true, only builds AFID events without running the hub.",
    )

    def analyze_data(
        self,
        data: ServiceabilityDataModel,
        args: Optional[ServiceabilityAnalyzerArgs] = None,
    ) -> TaskResult:
        if args is None:
            self.result.status = ExecutionStatus.NOT_RAN
            self.result.message = "ServiceabilityAnalyzerArgs are required"
            return self.result

        parent = self.parent or self.__class__.__name__
        result = analyze_serviceability_window(
            data,
            args,
            logger=self.logger,
            parent=parent,
        )
        if not result.ok:
            self.result.status = ExecutionStatus.ERROR
            self.result.message = result.message
            return self.result

        if result.serviceability is not None:
            self._append_hub_artifacts(result.serviceability)
            self._log_serviceability_solutions(result.serviceability)

        self.result.status = ExecutionStatus.OK
        self.result.message = result.message
        return self.result

    def _append_hub_artifacts(self, block: ServiceabilityBlock) -> None:
        """Hook for subclasses to attach hub-derived analyzer artifacts."""

    def _log_serviceability_solutions(self, block: ServiceabilityBlock) -> None:
        parent = self.parent or self.__class__.__name__
        for line in format_serviceability_solution_lines(block):
            self.logger.info("(%s) %s", parent, line)
