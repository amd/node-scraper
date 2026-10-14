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

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus
from nodescraper.models import TaskResult
from nodescraper.plugins.inband.dmesg.dmesg_collector import DmesgCollector
from nodescraper.plugins.inband.dmesg.dmesg_plugin import DmesgPlugin
from nodescraper.plugins.registers.register_decode_plugin import RegisterDecodePlugin
from nodescraper.plugins.registers.register_tool import tool_rows
from nodescraper.utils import resolve_log_dir_name

from .collector_args import McaRegisterDecodeCollectorArgs
from .mca_register_decode_analyzer import McaRegisterDecodeAnalyzer
from .mca_register_decode_collector import McaRegisterDecodeCollector
from .mca_register_decode_data import McaRegisterDecodeDataModel


def interval_rows(intervals: Any) -> list[dict[str, int]]:
    """Serialize check_interval readings to cpu and seconds mappings.

    Args:
        intervals: Readings returned by the register tool.

    Returns:
        One mapping per logical CPU.
    """
    rows = []
    for interval in intervals:
        if isinstance(interval, dict):
            cpu = int(interval["cpu"])
            seconds = int(interval["seconds"])
        else:
            cpu = int(interval.cpu)
            seconds = int(interval.seconds)
        rows.append({"cpu": cpu, "seconds": seconds})
    return rows


class McaRegisterDecodePlugin(RegisterDecodePlugin):
    """Expose MCA register-tool steps for an installed entry point."""

    DATA_MODEL = McaRegisterDecodeDataModel
    COLLECTOR = McaRegisterDecodeCollector
    ANALYZER = McaRegisterDecodeAnalyzer
    COLLECTOR_ARGS = McaRegisterDecodeCollectorArgs

    def __init__(
        self,
        system_info,
        tool_group: Optional[str] = None,
        tool_name: Optional[str] = None,
        **kwargs,
    ):
        """Store the register tool and an empty check_interval reading.

        Args:
            system_info: System this plugin runs against.
            tool_group: Entry-point group used to discover the register tool.
            tool_name: Entry-point name. Required when more than one tool is installed.
            kwargs: Arguments forwarded to the plugin base.
        """
        super().__init__(system_info, tool_group=tool_group, tool_name=tool_name, **kwargs)
        self.check_intervals: list[dict[str, int]] = []

    def _remote_message(self) -> str:
        """Return the message used when an MCA step runs on a remote system.

        Returns:
            Remote-system message.
        """
        return "MCA register decode is only supported on local"

    def get_check_intervals(self, threads: Optional[list[int]] = None) -> TaskResult:
        """Read check_interval for each logical CPU.

        Args:
            threads: Logical CPU indices. None reads every online CPU.

        Returns:
            OK with the readings stored on check_intervals.
        """
        self._begin("get_check_intervals")
        remote = self._reject_remote()
        if remote is not None:
            return remote
        try:
            method = self._optional_method("get_check_intervals")
            if method is None:
                return self.result
            self.check_intervals = interval_rows(method(threads=threads))
        except Exception as exc:
            return self._fail(f"MCA check_interval read failed: {exc}")
        self.result.status = ExecutionStatus.OK
        self.result.message = f"Read check_interval for {len(self.check_intervals)} logical CPU(s)"
        self.result.details = {"intervals": self.check_intervals}
        self._log_event(
            category=EventCategory.RAS,
            description=self.result.message,
            data={"intervals": self.check_intervals},
            priority=EventPriority.INFO,
        )
        return self.result

    def set_check_interval(self, seconds: int, threads: Optional[list[int]] = None) -> TaskResult:
        """Write check_interval for the selected logical CPUs.

        Args:
            seconds: Interval in seconds. Zero disables kernel MCA polling.
            threads: Logical CPU indices. None updates every online CPU.

        Returns:
            OK with the number of CPUs written, or ERROR when none were written.
        """
        self._begin("set_check_interval")
        remote = self._reject_remote()
        if remote is not None:
            return remote
        try:
            method = self._optional_method("set_check_interval")
            if method is None:
                return self.result
            written = int(method(seconds, threads=threads))
        except Exception as exc:
            return self._fail(f"MCA check_interval write failed: {exc}")
        if written <= 0:
            return self._fail("failed to set MCA check_interval")
        self.result.status = ExecutionStatus.OK
        self.result.message = f"Set check_interval to {seconds} on {written} logical CPU(s)"
        self.result.details = {"seconds": seconds, "written": written}
        self._log_event(
            category=EventCategory.RAS,
            description=self.result.message,
            priority=EventPriority.INFO,
        )
        return self.result

    def decode_dmesg(self, gpu: Optional[str] = None) -> TaskResult:
        """Decode MCA records from the dmesg log already collected in this run.

        Args:
            gpu: GPU project name. Required by the register tool when the log has a GPU bank.

        Returns:
            OK with decoded dmesg records, or WARNING when the log is missing.
        """
        self._begin("decode_dmesg")
        remote = self._reject_remote()
        if remote is not None:
            return remote
        if self.data is None or not isinstance(self.data, McaRegisterDecodeDataModel):
            return self._fail("No MCA register data is available")
        data = self.data
        log_file = self._collected_dmesg_path()
        if log_file is None:
            data.dmesg_decoded_records = []
            self.result.status = ExecutionStatus.WARNING
            self.result.message = "Collected dmesg log was not found"
            self._log_event(
                category=EventCategory.OS,
                description=self.result.message,
                priority=EventPriority.WARNING,
                console_log=True,
            )
            return self.result
        try:
            method = self._optional_method("decode_dmesg")
            if method is None:
                return self.result
            text = Path(log_file).read_text(encoding="utf-8")
            data.dmesg_decoded_records = tool_rows(method(text, gpu=gpu))
        except Exception as exc:
            return self._fail(f"MCA dmesg decode failed: {exc}")
        count = len(data.dmesg_decoded_records or [])
        self.result.status = ExecutionStatus.OK
        self.result.message = f"Decoded {count} dmesg MCA record(s)"
        self._log_event(
            category=EventCategory.RAS,
            description=self.result.message,
            data={"dmesg_records": self.data.dmesg_decoded_records},
            priority=EventPriority.INFO,
        )
        return self.result

    def clear(self, threads: Optional[list[int]] = None, wait_seconds: float = 2.0) -> TaskResult:
        """Drain MCA banks through the register tool.

        Args:
            threads: Logical CPU indices. None drains every online CPU.
            wait_seconds: Seconds to wait while the kernel drains the banks.

        Returns:
            OK with the number of CPUs cleared.
        """
        self._begin("clear")
        remote = self._reject_remote()
        if remote is not None:
            return remote
        try:
            method = self._optional_method("clear")
            if method is None:
                return self.result
            cleared = int(method(threads=threads, wait_seconds=wait_seconds))
        except Exception as exc:
            return self._fail(f"MCA register clear failed: {exc}")
        self.result.status = ExecutionStatus.OK
        self.result.message = f"Cleared MCA registers on {cleared} logical CPU(s)"
        self.result.details = {"cleared": cleared}
        self._log_event(
            category=EventCategory.RAS,
            description=self.result.message,
            priority=EventPriority.INFO,
        )
        return self.result

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
