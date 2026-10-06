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

from nodescraper.base import InBandDataCollector
from nodescraper.enums import (
    EventCategory,
    EventPriority,
    ExecutionStatus,
    OSFamily,
    SystemLocation,
)
from nodescraper.models import TaskResult

from .collector_args import RegisterDecodeCollectorArgs
from .register_decode_data import RegisterDecodeDataModel
from .register_tool import discover_register_tool


class RegisterDecodeCollector(
    InBandDataCollector[RegisterDecodeDataModel, RegisterDecodeCollectorArgs]
):
    """Collect register data through an installed register-tool entry point."""

    DATA_MODEL = RegisterDecodeDataModel
    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.LINUX}
    SUPPORTED_SKUS = {"MI450", "MI455", "MI4XX"}

    def collect_data(
        self, args: Optional[RegisterDecodeCollectorArgs] = None
    ) -> tuple[TaskResult, Optional[RegisterDecodeDataModel]]:
        """Collect registers with the discovered register tool.

        Args:
            args: Collector arguments for tool selection and scan options.

        Returns:
            Task result and collected records, or None when collection fails.
        """
        if args is None:
            args = RegisterDecodeCollectorArgs()
        if self.system_info.location == SystemLocation.REMOTE:
            message = "Register decode is only supported on local"
            self.result.status = ExecutionStatus.NOT_RAN
            self.result.message = message
            self._log_event(
                category=EventCategory.RAS,
                description=message,
                priority=EventPriority.INFO,
                console_log=True,
            )
            return self.result, None
        try:
            tool = discover_register_tool(name=args.tool_name, group=args.tool_group)
            health = tool.health_check()
            if health != 0:
                self._fail(f"Register tool health check failed with status {health}")
                return self.result, None
            collection = tool.collect(
                threads=args.threads,
                banks=args.banks,
                verbose=args.verbose,
                capture_all=args.capture_all,
            )
            payload = collection.model_dump(mode="json")
        except Exception as exc:
            self._fail(f"Register collect failed: {exc}")
            return self.result, None

        data = RegisterDecodeDataModel(stats=payload.get("stats"), records=list(payload["records"]))
        self.result.status = ExecutionStatus.OK
        self.result.message = f"Collected {len(data.records)} register record(s)"
        self._log_event(
            category=EventCategory.RAS,
            description=self.result.message,
            data={"record_count": len(data.records)},
            priority=EventPriority.INFO,
        )
        return self.result, data

    def _fail(self, message: str) -> None:
        """Record a collection failure.

        Args:
            message: Failure text stored on the task result.
        """
        self.result.status = ExecutionStatus.ERROR
        self.result.message = message
        self._log_event(
            category=EventCategory.RAS,
            description=message,
            priority=EventPriority.ERROR,
            console_log=True,
        )
