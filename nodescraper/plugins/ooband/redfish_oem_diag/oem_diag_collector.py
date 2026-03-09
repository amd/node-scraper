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
from pathlib import Path
from typing import Any, Optional

from nodescraper.base import RedfishDataCollector
from nodescraper.connection.redfish import collect_oem_diagnostic_data
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.models import TaskResult
from nodescraper.utils import pascal_to_snake

from .collector_args import RedfishOemDiagCollectorArgs
from .oem_diag_data import OemDiagTypeResult, RedfishOemDiagDataModel


class RedfishOemDiagCollector(
    RedfishDataCollector[RedfishOemDiagDataModel, RedfishOemDiagCollectorArgs]
):
    """Collects Redfish OEM diagnostic logs (e.g. JournalControl, AllLogs) via LogService.CollectDiagnosticData."""

    DATA_MODEL = RedfishOemDiagDataModel

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.log_path = kwargs.pop("log_path", None)
        super().__init__(*args, **kwargs)

    def collect_data(
        self, args: Optional[RedfishOemDiagCollectorArgs] = None
    ) -> tuple[TaskResult, Optional[RedfishOemDiagDataModel]]:
        """Run OEM diagnostic collection for each type in args.oem_diagnostic_types."""
        if args is None:
            args = RedfishOemDiagCollectorArgs()
        types_to_collect = list(args.oem_diagnostic_types) if args.oem_diagnostic_types else []
        if not types_to_collect:
            self.result.message = "No OEM diagnostic types configured"
            self.result.status = ExecutionStatus.NOT_RAN
            return self.result, None

        if self.log_path:
            output_dir = (
                Path(self.log_path)
                / pascal_to_snake(self.parent or "")
                / pascal_to_snake(self.__class__.__name__)
            )
        else:
            output_dir = None

        if output_dir is not None:
            self.logger.info(
                "(RedfishOemDiagPlugin) Writing diagnostic archives to: %s",
                output_dir.resolve(),
            )

        results: dict[str, OemDiagTypeResult] = {}
        validate = bool(args.oem_diagnostic_types_allowable)
        for oem_type in types_to_collect:
            log_bytes, metadata, err = collect_oem_diagnostic_data(
                self.connection,
                log_service_path=args.log_service_path,
                oem_diagnostic_type=oem_type,
                task_timeout_s=args.task_timeout_s,
                output_dir=output_dir,
                validate_type=validate,
                allowed_types=args.oem_diagnostic_types_allowable,
            )
            if err:
                self._log_event(
                    category=EventCategory.RUNTIME,
                    description=f"OEM diag {oem_type!r}: {err}",
                    priority=EventPriority.WARNING,
                    console_log=True,
                )
                results[oem_type] = OemDiagTypeResult(success=False, error=err, metadata=None)
            else:
                results[oem_type] = OemDiagTypeResult(success=True, error=None, metadata=metadata)

        success_count = sum(1 for r in results.values() if r.success)
        self.result.message = f"OEM diag: {success_count}/{len(results)} types collected"
        self.result.status = ExecutionStatus.OK if success_count else ExecutionStatus.ERROR
        return self.result, RedfishOemDiagDataModel(results=results)
