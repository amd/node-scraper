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
from nodescraper.plugins.serviceability.afid_events import build_afid_events_from_data
from nodescraper.plugins.serviceability.analyzer_args import ServiceabilityAnalyzerArgs
from nodescraper.plugins.serviceability.se_models import ServiceabilityBlock
from nodescraper.plugins.serviceability.se_runner import SeRunError, run_se
from nodescraper.plugins.serviceability.serviceability_data import (
    ServiceabilityDataModel,
)


class Mi3xxAnalyzer(DataAnalyzer[ServiceabilityDataModel, ServiceabilityAnalyzerArgs]):
    """Build AFID events from collected data and run the serviceability engine."""

    DATA_MODEL = ServiceabilityDataModel

    def analyze_data(
        self,
        data: ServiceabilityDataModel,
        args: Optional[ServiceabilityAnalyzerArgs] = None,
    ) -> TaskResult:
        if args is None:
            self.result.status = ExecutionStatus.NOT_RAN
            self.result.message = "ServiceabilityAnalyzerArgs are required"
            return self.result

        events = data.afid_events or build_afid_events_from_data(data)
        data.afid_events = events

        if args.skip_engine:
            data.serviceability = ServiceabilityBlock(afid_events=events)
            self.result.status = ExecutionStatus.OK
            self.result.message = f"Built {len(events)} AFID event(s); engine skipped"
            return self.result

        try:
            block = run_se(
                engine_backend=args.engine_backend,
                engine_python_module=args.engine_python_module,
                engine_executable=args.engine_executable,
                engine_entry_point=args.engine_entry_point,
                afid_events=events,
                afid_sag_path=args.afid_sag_path,  # type: ignore[arg-type]
                extra_args=args.engine_extra_args or None,
                timeout_seconds=args.engine_timeout_seconds,
            )
        except (SeRunError, ValueError) as exc:
            self.result.status = ExecutionStatus.ERROR
            self.result.message = str(exc)
            return self.result

        data.serviceability = block
        self.result.status = ExecutionStatus.OK
        self.result.message = (
            f"Serviceability engine: {len(block.solution)} solution(s) "
            f"from {len(events)} event(s)"
        )
        return self.result
