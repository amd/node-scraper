###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
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
import time
from typing import Optional

from nodescraper.base import InBandDataCollector
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult

from .collector_args import ProcessCollectorArgs
from .processdata import ProcessDataModel


def _parse_aggregate_cpu_from_proc_stat(proc_stat: str) -> Optional[tuple[int, int]]:
    """Return total and idle-plus-I/O-wait jiffies from ``/proc/stat``.

    Guest fields are excluded from the total because Linux includes them in
    the user and nice fields.
    """
    for line in proc_stat.splitlines():
        if not line.startswith("cpu "):
            continue

        parts = line.split()
        if len(parts) < 6:
            return None
        try:
            values = [int(value) for value in parts[1:]]
        except ValueError:
            return None

        # guest and guest_nice are already included in user and nice.
        return sum(values[:8]), values[3] + values[4]
    return None


def _global_non_idle_percent(total1: int, idle1: int, total2: int, idle2: int) -> float:
    """Return aggregate non-idle CPU percentage between two samples."""
    total_delta = total2 - total1
    if total_delta <= 0:
        return 0.0

    idle_delta = idle2 - idle1
    percentage = 100.0 * (1.0 - idle_delta / total_delta)
    return round(max(0.0, min(100.0, percentage)), 6)


def _parse_proc_pid_stat(stat_line: str) -> Optional[tuple[int, int]]:
    """Return a process PID and its user-plus-system jiffies."""
    stat_line = stat_line.strip()
    if not stat_line:
        return None

    try:
        paren_end = stat_line.rfind(") ")
        if paren_end < 0:
            return None
        pid = int(stat_line[:paren_end].split(maxsplit=1)[0])
        fields = stat_line[paren_end + 2 :].split()
        if len(fields) < 13:
            return None
        return pid, int(fields[11]) + int(fields[12])
    except ValueError:
        return None


def _parse_proc_stat_dump(dump_stdout: str) -> tuple[dict[int, int], set[int]]:
    """Parse bulk ``pid|stat`` output and sampler PIDs."""
    jiffies_by_pid: dict[int, int] = {}
    sampler_pids: set[int] = set()

    for line in dump_stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("__SAMPLER__:"):
            try:
                sampler_pids.add(int(stripped.split(":", 1)[1]))
            except ValueError:
                pass
            continue
        if "|" not in line:
            continue

        pid_text, stat_line = line.split("|", 1)
        try:
            prefixed_pid = int(pid_text)
        except ValueError:
            continue

        parsed = _parse_proc_pid_stat(stat_line)
        if parsed is None:
            continue
        stat_pid, jiffies = parsed
        if stat_pid == prefixed_pid:
            jiffies_by_pid[prefixed_pid] = jiffies

    return jiffies_by_pid, sampler_pids


def _top_process_cpu_shares(
    sample1: dict[int, int],
    sample2: dict[int, int],
    total_delta: int,
    top_n: int,
    exclude_pids: set[int],
) -> list[tuple[int, float]]:
    """Rank processes by their share of aggregate CPU jiffies."""
    if top_n <= 0:
        return []

    rows: list[tuple[int, float, int]] = []
    for pid in sample2:
        if pid in exclude_pids:
            continue
        delta = max(0, sample2.get(pid, 0) - sample1.get(pid, 0))
        percentage = 100.0 * delta / total_delta if total_delta > 0 else 0.0
        rows.append((pid, percentage, delta))

    rows.sort(key=lambda row: (row[2], row[1]), reverse=True)
    return [(pid, percentage) for pid, percentage, _ in rows[:top_n]]


def _parse_comm_dump(dump_stdout: str) -> dict[int, str]:
    """Parse ``pid:comm`` lines into process names keyed by PID."""
    processes: dict[int, str] = {}
    for line in dump_stdout.splitlines():
        if ":" not in line:
            continue
        pid_text, command = line.split(":", 1)
        try:
            processes[int(pid_text)] = command.strip()
        except ValueError:
            continue
    return processes


_STAT_DUMP_SHELL = (
    'printf "__SAMPLER__:%s\\n" "$$"; '
    "for f in /proc/[0-9]*/stat; do "
    '[ -r "$f" ] || continue; '
    'pid="${f#/proc/}"; pid="${pid%/stat}"; '
    '[ "$pid" = "$$" ] && continue; '
    'printf "%s|" "$pid"; cat "$f" 2>/dev/null || true; printf "\\n"; '
    "done"
)


class ProcessCollector(InBandDataCollector[ProcessDataModel, ProcessCollectorArgs]):
    """Collect aggregate CPU usage and top processes from Linux procfs."""

    SUPPORTED_OS_FAMILY: set[OSFamily] = {OSFamily.LINUX}

    DATA_MODEL = ProcessDataModel
    CMD_PROC_STAT = "cat /proc/stat"
    CMD_PROCESS_STAT = _STAT_DUMP_SHELL
    CMD_PROCESS_NAMES = (
        "for p in {pids}; do "
        'printf "%s:" "$p"; '
        "cat /proc/$p/comm 2>/dev/null || true; "
        'printf "\\n"; '
        "done"
    )

    def _collect_procfs_cpu(
        self, top_n_process: int, sample_interval_seconds: float
    ) -> tuple[Optional[float], list[tuple[str, str]]]:
        """Collect aggregate CPU usage and top process CPU shares."""
        stat1 = self._run_sut_cmd(self.CMD_PROC_STAT)
        if stat1.exit_code != 0:
            self.logger.warning(
                "Unable to read first aggregate CPU sample (exit code %s)", stat1.exit_code
            )
            return None, []
        dump1 = self._run_sut_cmd(self.CMD_PROCESS_STAT, log_artifact=False)
        if dump1.exit_code != 0:
            self.logger.warning(
                "Unable to read first process CPU sample (exit code %s)", dump1.exit_code
            )
            return None, []

        time.sleep(sample_interval_seconds)

        stat2 = self._run_sut_cmd(self.CMD_PROC_STAT)
        if stat2.exit_code != 0:
            self.logger.warning(
                "Unable to read second aggregate CPU sample (exit code %s)", stat2.exit_code
            )
            return None, []
        dump2 = self._run_sut_cmd(self.CMD_PROCESS_STAT, log_artifact=False)
        if dump2.exit_code != 0:
            self.logger.warning(
                "Unable to read second process CPU sample (exit code %s)", dump2.exit_code
            )
            return None, []

        aggregate1 = _parse_aggregate_cpu_from_proc_stat(stat1.stdout)
        aggregate2 = _parse_aggregate_cpu_from_proc_stat(stat2.stdout)
        if aggregate1 is None or aggregate2 is None:
            sample = "first" if aggregate1 is None else "second"
            output = stat1.stdout if aggregate1 is None else stat2.stdout
            self._log_event(
                category=EventCategory.OS,
                description=f"Could not parse aggregate cpu line from /proc/stat ({sample} sample)",
                data={"proc_stat_preview": output[:200]},
                priority=EventPriority.ERROR,
            )
            return None, []

        total1, idle1 = aggregate1
        total2, idle2 = aggregate2
        cpu_usage = _global_non_idle_percent(total1, idle1, total2, idle2)
        total_delta = max(0, total2 - total1)

        sample1, excluded1 = _parse_proc_stat_dump(dump1.stdout)
        sample2, excluded2 = _parse_proc_stat_dump(dump2.stdout)
        top_processes = _top_process_cpu_shares(
            sample1,
            sample2,
            total_delta,
            top_n_process,
            excluded1 | excluded2,
        )

        if not top_processes:
            return cpu_usage, []

        pids = " ".join(str(pid) for pid, _percentage in top_processes)
        process_names = self._run_sut_cmd(self.CMD_PROCESS_NAMES.format(pids=pids))
        names = _parse_comm_dump(process_names.stdout) if process_names.exit_code == 0 else {}
        processes = [
            (names.get(pid) or f"pid_{pid}", f"{percentage:.1f}")
            for pid, percentage in top_processes
        ]
        return cpu_usage, processes

    def collect_data(
        self, args: Optional[ProcessCollectorArgs] = None
    ) -> tuple[TaskResult, Optional[ProcessDataModel]]:
        """Collect process data from the system.

        Args:
            args (Optional[ProcessCollectorArgs], optional): process collection arguments. Defaults to None.

        Returns:
            tuple[TaskResult, Optional[ProcessDataModel]]: tuple containing the task result and the collected process data model or None if no data was collected.
        """
        if args is None:
            args = ProcessCollectorArgs()

        process_data = ProcessDataModel()
        cpu_usage, processes = self._collect_procfs_cpu(
            args.top_n_process, args.sample_interval_seconds
        )
        if cpu_usage is not None:
            process_data.cpu_usage = cpu_usage
            process_data.processes = processes
            self._log_event(
                category=EventCategory.PROCESS_READ,
                description="Process data collected",
                priority=EventPriority.INFO,
            )
            self.result.message = "Process data collected"
            self.result.status = ExecutionStatus.OK
            return self.result, process_data

        self._log_event(
            category=EventCategory.OS,
            description="Process data not found",
            priority=EventPriority.ERROR,
        )
        self.result.message = "Process data not found"
        self.result.status = ExecutionStatus.EXECUTION_FAILURE
        return self.result, None
