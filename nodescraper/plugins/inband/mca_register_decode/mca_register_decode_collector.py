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
from nodescraper.plugins.inband.dmesg.dmesg_collector import DmesgCollector
from nodescraper.plugins.inband.dmesg.dmesg_plugin import DmesgPlugin
from nodescraper.utils import resolve_log_dir_name

from .collector_args import McaRegisterDecodeCollectorArgs
from .mca_register_decode_data import McaRegisterDecodeDataModel
from .mca_register_session import McaRegisterDecodeSession
from .register_tool import discover_register_tool


class McaRegisterDecodeCollector(
    InBandDataCollector[McaRegisterDecodeDataModel, McaRegisterDecodeCollectorArgs]
):
    """Collect MCA register data through an installed register-tool entry point."""

    DATA_MODEL = McaRegisterDecodeDataModel
    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.LINUX}
    SUPPORTED_SKUS = {"MI450", "MI455", "MI4XX"}
    _dmesg_error: Optional[str] = None

    def collect_data(
        self, args: Optional[McaRegisterDecodeCollectorArgs] = None
    ) -> tuple[TaskResult, Optional[McaRegisterDecodeDataModel]]:
        """Collect and decode MCA registers, then decode MCAs that reached dmesg.

        Args:
            args: Collector arguments for tool selection and scan options.

        Returns:
            Task result and collected records, or None when collection fails.
        """
        if args is None:
            args = McaRegisterDecodeCollectorArgs()
        self._dmesg_error = None
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
            return self.result, None
        try:
            tool = discover_register_tool(name=args.tool_name, group=args.tool_group)
        except Exception as exc:
            self._fail(f"MCA register collect failed: {exc}")
            return self.result, None

        session = McaRegisterDecodeSession(tool, threads=args.threads)
        if args.manage_check_interval:
            health = session.prepare()
        else:
            health = int(tool.health_check())
        if health != 0:
            self._fail(f"MCA register tool health check failed with status {health}")
            return self.result, None

        error: Optional[Exception] = None
        payload = None
        suspended = False
        try:
            if args.manage_check_interval:
                written = session.suspend_polling()
                suspended = True
                if written <= 0:
                    raise RuntimeError("failed to disable MCA kernel polling")
            payload = session.capture(
                banks=args.banks,
                verbose=args.verbose,
                capture_all=args.capture_all,
                read_dmesg=self._collected_dmesg,
                gpu=args.gpu,
                wait_seconds=args.wait_seconds,
            )
        except Exception as exc:
            error = exc
        if payload is None and (suspended or not args.manage_check_interval):
            try:
                session.drain(wait_seconds=args.wait_seconds)
            except Exception as exc:
                error = error or exc
        if args.manage_check_interval and session.saved_intervals:
            try:
                session.restore()
            except Exception as exc:
                error = error or exc
        if error is not None or payload is None:
            self._fail(f"MCA register collect failed: {error}")
            return self.result, None

        data = McaRegisterDecodeDataModel(
            stats=payload["stats"],
            records=payload["records"],
            decoded_records=payload["decoded_records"],
            dmesg_decoded_records=payload["dmesg_decoded_records"],
        )
        register_count = len(data.decoded_records or [])
        dmesg_count = len(data.dmesg_decoded_records or [])
        self.result.message = (
            f"Collected {len(data.records)} MCA register record(s) and decoded "
            f"{register_count} MSR record(s) and {dmesg_count} dmesg record(s)"
        )
        if self._dmesg_error is None:
            self.result.status = ExecutionStatus.OK
            priority = EventPriority.INFO
        else:
            self.result.status = ExecutionStatus.WARNING
            priority = EventPriority.WARNING
        self._log_event(
            category=EventCategory.RAS,
            description=self.result.message,
            data={
                "record_count": len(data.records),
                "decoded_count": register_count,
                "dmesg_decoded_count": dmesg_count,
            },
            priority=priority,
        )
        return self.result, data

    def _collected_dmesg(self) -> Optional[str]:
        """Read the kernel log already written by the dmesg collector.

        Returns:
            Log text, or None when that log is not in this run.
        """
        self._dmesg_error = None
        log_file = self._collected_dmesg_path()
        if log_file is None:
            self._dmesg_error = "collected dmesg log was not found"
            self._log_event(
                category=EventCategory.OS,
                description="Collected dmesg log was not found",
                priority=EventPriority.WARNING,
                console_log=True,
            )
            return None
        with open(log_file, encoding="utf-8") as handle:
            return handle.read()

    def _collected_dmesg_path(self) -> Optional[str]:
        """Find the dmesg collector log for this run.

        Returns:
            Path to the newest collected dmesg log, or None.
        """
        if not self.log_path:
            return None
        plugin_dir = resolve_log_dir_name(DmesgPlugin.__name__)
        collector_dir = resolve_log_dir_name(DmesgCollector.__name__)
        current = Path(self.log_path)
        for base in (current, *current.parents):
            folder = base / plugin_dir / collector_dir
            if not folder.is_dir():
                continue
            logs = [path for path in folder.glob("dmesg*.log") if path.is_file()]
            if logs:
                newest = max(logs, key=lambda path: path.stat().st_mtime)
                return str(newest)
        return None

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
