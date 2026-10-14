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
from typing import Any, Callable, Optional, Sequence


def _dump(value: Any) -> Any:
    """Serialize a register-tool model to JSON-ready data.

    Args:
        value: Model, mapping, or None.

    Returns:
        JSON-ready value, or None when value is None.
    """
    if value is None:
        return None
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return dump(mode="json")
    return value


def _rows(value: Any) -> list[dict[str, Any]]:
    """Serialize register-tool records to a list of mappings.

    Args:
        value: Collection result or a sequence of records.

    Returns:
        JSON-ready record mappings.
    """
    rows = getattr(value, "records", value)
    dumped = []
    for row in rows:
        item = _dump(row)
        if not isinstance(item, dict):
            raise TypeError("register tool record is not a mapping")
        dumped.append(item)
    return dumped


class McaRegisterDecodeSession:
    """Hold saved check_interval values across one register-tool pass."""

    def __init__(self, tool: Any, threads: Optional[Sequence[int]] = None) -> None:
        """Store the register tool and the logical CPUs it should touch.

        Args:
            tool: Discovered register tool.
            threads: Logical CPU indices. None selects every online CPU.
        """
        self.tool = tool
        self.threads = threads
        self.saved_intervals: list[Any] = []

    def prepare(self) -> int:
        """Check MSR access and save each logical CPU's check_interval.

        Returns:
            Zero when the register tool is usable. Non-zero leaves saved intervals empty.
        """
        health = int(self.tool.health_check())
        if health != 0:
            return health
        self.saved_intervals = list(self.tool.get_check_intervals(threads=self.threads))
        return 0

    def suspend_polling(self) -> int:
        """Disable kernel MCA polling by setting check_interval to 0.

        Returns:
            Number of logical CPUs updated.
        """
        return int(self.tool.set_check_interval(0, threads=self.threads))

    def capture(
        self,
        banks: Optional[Sequence[int]] = None,
        verbose: bool = False,
        capture_all: bool = False,
        read_dmesg: Optional[Callable[[], Optional[str]]] = None,
        gpu: Optional[str] = None,
        wait_seconds: float = 2.0,
    ) -> dict[str, Any]:
        """Collect MSR MCAs, decode them, decode dmesg, then drain the banks.

        Args:
            banks: Register bank indices. None scans every bank.
            verbose: Ask the register tool to emit scan diagnostics.
            capture_all: Keep banks that do not have a pending error.
            read_dmesg: Callable that returns kernel-log text after MSR decode.
            gpu: GPU project name passed to dmesg decode.
            wait_seconds: Seconds to wait while the kernel drains MCA banks.

        Returns:
            Collected stats, raw records, decoded MSR records, and decoded dmesg records.
        """
        collection = self.tool.collect(
            threads=self.threads,
            banks=banks,
            verbose=verbose,
            capture_all=capture_all,
        )
        decoded = self.tool.decode_records(collection)
        dmesg_text = read_dmesg() if read_dmesg is not None else None
        if dmesg_text is None:
            dmesg_rows: list[dict[str, Any]] = []
        else:
            dmesg_rows = _rows(self.tool.decode_dmesg(dmesg_text, gpu=gpu))
        self.drain(wait_seconds=wait_seconds)
        return {
            "stats": _dump(getattr(collection, "stats", None)),
            "records": _rows(collection),
            "decoded_records": _rows(decoded),
            "dmesg_decoded_records": dmesg_rows,
        }

    def drain(self, wait_seconds: float = 2.0) -> int:
        """Set check_interval to 1 so the kernel drains MCA banks, then restore that current value.

        Args:
            wait_seconds: Seconds to wait while the kernel polls the banks.

        Returns:
            Number of logical CPUs restored by the register tool.
        """
        return int(self.tool.clear(threads=self.threads, wait_seconds=wait_seconds))

    def restore(self) -> int:
        """Write the check_interval values saved by prepare back to each logical CPU.

        Returns:
            Number of logical CPUs restored.
        """
        grouped: dict[int, list[int]] = {}
        for interval in self.saved_intervals:
            if isinstance(interval, dict):
                cpu = int(interval["cpu"])
                seconds = int(interval["seconds"])
            else:
                cpu = int(interval.cpu)
                seconds = int(interval.seconds)
            grouped.setdefault(seconds, []).append(cpu)
        restored = 0
        for seconds, cpus in grouped.items():
            restored += int(self.tool.set_check_interval(seconds, cpus))
        return restored
