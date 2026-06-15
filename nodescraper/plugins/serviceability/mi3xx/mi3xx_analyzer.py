###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, distribute, sublicense, and/or sell
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
from nodescraper.plugins.serviceability.cper_decode import (
    CperDecodeError,
    decode_cper_raw_attachments,
)
from nodescraper.plugins.serviceability.se_adapter import (
    format_serviceability_solution_lines,
)
from nodescraper.plugins.serviceability.se_models import ServiceabilityBlock
from nodescraper.plugins.serviceability.se_runner import SeRunError, run_service_hub
from nodescraper.plugins.serviceability.serviceability_data import (
    ServiceabilityDataModel,
)


class MI3XXAnalyzer(DataAnalyzer[ServiceabilityDataModel, ServiceabilityAnalyzerArgs]):
    """Build AFID events from collected data and run the configured service hub."""

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
            self.result.message = f"Built {len(events)} AFID event(s); hub skipped"
            self._log_serviceability_solutions(data.serviceability)
            return self.result

        parent = self.parent or self.__class__.__name__
        cper_data = data.cper_data or {}
        if data.cper_raw and not cper_data:
            if not args.cper_decode_module:
                self.logger.warning(
                    "(%s) %d CPER attachment(s) collected but cper_decode_module is "
                    "not set in analysis_args; skipping CPER decode",
                    parent,
                    len(data.cper_raw),
                )
            else:
                self.logger.info(
                    "(%s) Decoding %d CPER attachment(s) via %s.%s",
                    parent,
                    len(data.cper_raw),
                    args.cper_decode_module,
                    args.cper_decode_method,
                )
                try:
                    cper_data = decode_cper_raw_attachments(
                        data.cper_raw,
                        cper_decode_module=args.cper_decode_module,
                        cper_decode_method=args.cper_decode_method,
                        logger=self.logger,
                    )
                    data.cper_data = cper_data
                    self.logger.info(
                        "(%s) CPER decode finished: %d of %d attachment(s) decoded",
                        parent,
                        len(cper_data),
                        len(data.cper_raw),
                    )
                except CperDecodeError as exc:
                    self.logger.warning(
                        "(%s) %s; continuing without decoded CPER",
                        parent,
                        exc,
                    )
        elif cper_data:
            self.logger.info(
                "(%s) Using %d pre-decoded CPER record(s) from collection",
                parent,
                len(cper_data),
            )

        try:
            block = run_service_hub(
                engine_python_module=args.engine_python_module,  # type: ignore[arg-type]
                engine_display_name=args.engine_display_name,
                afid_events=events,
                afid_sag_path=args.afid_sag_path,  # type: ignore[arg-type]
                rf_events=data.rf_events,
                cper_data=cper_data or None,
                hub_options=args.resolved_hub_options(),
                engine_analyze_method=args.engine_analyze_method,
                engine_init_path_kwarg=args.engine_init_path_kwarg,
            )
        except (SeRunError, ValueError) as exc:
            self.result.status = ExecutionStatus.ERROR
            self.result.message = str(exc)
            return self.result

        data.serviceability = block
        self._log_serviceability_solutions(block)
        engine_label = args.engine_display_name or args.engine_python_module
        self.result.status = ExecutionStatus.OK
        cper_summary = ""
        if cper_data:
            cper_summary = f", {len(cper_data)} decoded CPER(s)"
        elif data.cper_raw:
            cper_summary = f", {len(data.cper_raw)} CPER attachment(s) not decoded"
        ver_bits: list[str] = []
        if block.hub_version:
            ver_bits.append(f"hub {block.hub_version}")
        if block.afid_sag_file_version:
            ver_bits.append(f"AFID_SAG {block.afid_sag_file_version}")
        ver_suffix = f" [{'; '.join(ver_bits)}]" if ver_bits else ""
        self.result.message = (
            f"{engine_label}: {len(block.solution)} solution(s) "
            f"from {len(data.rf_events)} Redfish event(s){cper_summary}{ver_suffix}"
        )
        return self.result

    def _log_serviceability_solutions(self, block: ServiceabilityBlock) -> None:
        parent = self.parent or self.__class__.__name__
        for line in format_serviceability_solution_lines(block):
            self.logger.info("(%s) %s", parent, line)
