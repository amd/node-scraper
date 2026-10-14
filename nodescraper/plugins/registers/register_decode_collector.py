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
from typing import Any, Optional

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
from .register_tool import discover_register_tool, dump_tool_value, tool_rows


class RegisterDecodeCollector(
    InBandDataCollector[RegisterDecodeDataModel, RegisterDecodeCollectorArgs]
):
    """Read registers through an installed register-tool entry point."""

    DATA_MODEL = RegisterDecodeDataModel
    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.LINUX}

    def collect_data(
        self, args: Optional[RegisterDecodeCollectorArgs] = None
    ) -> tuple[TaskResult, Optional[RegisterDecodeDataModel]]:
        """Read registers.

        Args:
            args: Collector arguments for tool selection.

        Returns:
            Task result and collected records, or None when collection fails.
        """
        if args is None:
            args = self._default_args()
        if self.system_info.location == SystemLocation.REMOTE:
            message = self._remote_message()
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
            collection = self._read_registers(tool, args)
        except Exception as exc:
            self._fail(f"{self._record_name()} collect failed: {exc}")
            return self.result, None

        data = self.DATA_MODEL(
            stats=dump_tool_value(getattr(collection, "stats", None)),
            records=tool_rows(collection),
        )
        self.result.status = ExecutionStatus.OK
        self.result.message = f"Collected {len(data.records)} {self._record_name()} record(s)"
        self._log_event(
            category=EventCategory.RAS,
            description=self.result.message,
            data={"record_count": len(data.records)},
            priority=EventPriority.INFO,
        )
        return self.result, data

    def _default_args(self) -> RegisterDecodeCollectorArgs:
        """Build collector args when the caller omitted them.

        Returns:
            Default collector args for this collector.
        """
        return RegisterDecodeCollectorArgs()

    def _record_name(self) -> str:
        """Return the record name used in result messages.

        Returns:
            Record name.
        """
        return "register"

    def _remote_message(self) -> str:
        """Return the message used when collection is remote.

        Returns:
            Remote-system message.
        """
        return "Register collection is only supported on local"

    def _read_registers(self, tool: Any, args: RegisterDecodeCollectorArgs) -> Any:
        """Read registers from the discovered tool.

        Args:
            tool: Discovered register tool.
            args: Collector arguments.

        Returns:
            Tool collection result.
        """
        return tool.collect()

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
