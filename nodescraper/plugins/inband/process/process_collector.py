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
from typing import Dict, List, Optional, Set, Tuple

from nodescraper.base import InBandDataCollector
from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.models import TaskResult

from .collector_args import ProcessCollectorArgs
from .processdata import ProcessDataModel


def _parse_aggregate_cpu_from_proc_stat(proc_stat: str) -> Optional[Tuple[int, int]]:
    """Aggregate ``cpu`` line from ``/proc/stat``: ``(total jiffies, idle+iowait)`` or ``None``."""
    for line in proc_stat.splitlines():
        if not line.startswith("cpu "):
            continue
        parts = line.split()
        if len(parts) < 6:
            return None
        try:
            nums = [int(parts[i]) for i in range(1, len(parts))]
        except ValueError:
            return None
        idle = nums[3] + nums[4]
        total = sum(nums)
        return total, idle
    return None


def _global_non_idle_percent(total1: int, idle1: int, total2: int, idle2: int) -> float:
    """Non-idle % over the interval between two aggregate cpu samples."""
    dt = total2 - total1
    if dt <= 0:
        return 0.0
    di = idle2 - idle1
    pct = 100.0 * (1.0 - di / dt)
    pct = max(0.0, min(100.0, pct))
    return round(pct, 6)


def _parse_proc_pid_stat(stat_line: str) -> Optional[Tuple[int, int]]:
    """Parse ``/proc/<pid>/stat`` body (without pid prefix). Return (pid, utime+stime)."""
    stat_line = stat_line.strip()
    if not stat_line:
        return None
    try:
        paren_end = stat_line.index(") ")
    except ValueError:
        return None
    head = stat_line[:paren_end]
    pid_str = head.split(maxsplit=1)[0]
    pid = int(pid_str)
    rest = stat_line[paren_end + 2 :].split()
    if len(rest) < 13:
        return None
    utime = int(rest[11])
    stime = int(rest[12])
    return pid, utime + stime


def _parse_proc_stat_dump(dump_stdout: str) -> Tuple[Dict[int, int], Set[int]]:
    """Parse bulk ``pid|statline`` lines; return (pid -> jiffies, sampler_pids to exclude).

    The shell dump prefixes one line ``__SAMPLER__:<pid>`` (see ``ProcessCollector.CMD_PROC_PID_STAT_DUMP``) so we
    can drop that subshell from rankings—it would otherwise show up as active CPU.
    """
    jiffies_by_pid: Dict[int, int] = {}
    exclude: Set[int] = set()
    for line in dump_stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("__SAMPLER__:"):
            try:
                exclude.add(int(stripped.split(":", 1)[1]))
            except ValueError:
                pass
            continue
        if "|" not in line:
            continue
        pid_str, stat_body = line.split("|", 1)
        try:
            prefix_pid = int(pid_str)
        except ValueError:
            continue
        parsed = _parse_proc_pid_stat(stat_body)
        if parsed is None:
            continue
        stat_pid, jf = parsed
        if stat_pid != prefix_pid:
            continue
        jiffies_by_pid[prefix_pid] = jf
    return jiffies_by_pid, exclude


def _parse_comm_dump(dump_stdout: str) -> Dict[int, str]:
    """Parse ``pid:comm`` lines from ``cat /proc/<pid>/comm`` batch."""
    out: Dict[int, str] = {}
    for line in dump_stdout.splitlines():
        if ":" not in line:
            continue
        pid_str, comm = line.split(":", 1)
        try:
            pid = int(pid_str)
        except ValueError:
            continue
        out[pid] = comm.strip()
    return out


def _top_process_cpu_shares(
    sample1: Dict[int, int],
    sample2: Dict[int, int],
    total_delta: int,
    top_n: int,
    exclude_pids: Set[int],
) -> List[Tuple[int, float]]:
    """Return up to ``top_n`` (pid, cpu_share_pct) sorted by jiffies delta descending."""
    if top_n <= 0:
        return []
    all_pids = set(sample1) | set(sample2)
    rows: List[Tuple[int, float, int]] = []
    for pid in all_pids:
        if pid in exclude_pids:
            continue
        j1 = sample1.get(pid, 0)
        j2 = sample2.get(pid, 0)
        delta = max(0, j2 - j1)
        if total_delta > 0:
            pct = 100.0 * delta / total_delta
        else:
            pct = 0.0
        rows.append((pid, pct, delta))
    rows.sort(key=lambda x: (x[2], x[1]), reverse=True)
    return [(pid, pct) for pid, pct, _ in rows[:top_n]]


class ProcessCollector(InBandDataCollector[ProcessDataModel, ProcessCollectorArgs]):
    """Linux process list and aggregate CPU usage from ``/proc`` (two samples; no ``top`` or ROCm SMI)."""

    SUPPORTED_OS_FAMILY: Set[OSFamily] = {OSFamily.LINUX}

    DATA_MODEL = ProcessDataModel

    CMD_PROC_STAT = "cat /proc/stat"
    # Lead with ``__SAMPLER__:<pid>`` so we exclude that subshell from top-N rankings.
    CMD_PROC_PID_STAT_DUMP = (
        'printf "__SAMPLER__:%s\\n" "$$"; '
        "for f in /proc/[0-9]*/stat; do "
        '[ -r "$f" ] || continue; '
        'pid="${f#/proc/}"; pid="${pid%/stat}"; '
        '[ "$pid" = "$$" ] && continue; '
        'printf "%s|" "$pid"; cat "$f" 2>/dev/null || true; printf "\\n"; '
        "done"
    )
    CMD_PROC_COMM_BATCH = (
        "for p in {pids}; do "
        'printf "%s:" "$p"; '
        "cat /proc/$p/comm 2>/dev/null || true; "
        'printf "\\n"; '
        "done"
    )

    def _collect_procfs_cpu(
        self,
        top_n_process: int,
        sample_interval_seconds: float,
    ) -> Tuple[Optional[float], List[Tuple[str, str]]]:
        """Return (cpu_usage, processes) from procfs; (None, []) on failure."""
        stat1 = self._run_sut_cmd(self.CMD_PROC_STAT)
        if stat1.exit_code != 0:
            return None, []
        dump1 = self._run_sut_cmd(self.CMD_PROC_PID_STAT_DUMP)
        if dump1.exit_code != 0:
            return None, []

        time.sleep(sample_interval_seconds)

        stat2 = self._run_sut_cmd(self.CMD_PROC_STAT)
        if stat2.exit_code != 0:
            return None, []
        dump2 = self._run_sut_cmd(self.CMD_PROC_PID_STAT_DUMP)
        if dump2.exit_code != 0:
            return None, []

        agg1 = _parse_aggregate_cpu_from_proc_stat(stat1.stdout)
        agg2 = _parse_aggregate_cpu_from_proc_stat(stat2.stdout)
        if agg1 is None:
            self._log_event(
                category=EventCategory.OS,
                description="Could not parse aggregate cpu line from /proc/stat (first sample)",
                data={"proc_stat_preview": stat1.stdout[:200]},
                priority=EventPriority.ERROR,
            )
            return None, []
        if agg2 is None:
            self._log_event(
                category=EventCategory.OS,
                description="Could not parse aggregate cpu line from /proc/stat (second sample)",
                data={"proc_stat_preview": stat2.stdout[:200]},
                priority=EventPriority.ERROR,
            )
            return None, []

        total1, idle1 = agg1
        total2, idle2 = agg2
        cpu_usage = _global_non_idle_percent(total1, idle1, total2, idle2)
        dt = total2 - total1
        t_delta = dt if dt > 0 else 0

        sample1, excl1 = _parse_proc_stat_dump(dump1.stdout)
        sample2, excl2 = _parse_proc_stat_dump(dump2.stdout)
        exclude = excl1 | excl2

        top_list = _top_process_cpu_shares(sample1, sample2, t_delta, top_n_process, exclude)
        pids = [pid for pid, _ in top_list]
        if not pids:
            processes: List[Tuple[str, str]] = []
        else:
            pid_str = " ".join(str(p) for p in pids)
            comm_res = self._run_sut_cmd(self.CMD_PROC_COMM_BATCH.format(pids=pid_str))
            if comm_res.exit_code != 0:
                comm_map: Dict[int, str] = {}
            else:
                comm_map = _parse_comm_dump(comm_res.stdout)
            processes = []
            for pid, pct in top_list:
                name = comm_map.get(pid, f"pid_{pid}")
                processes.append((name, f"{pct:.1f}"))

        return cpu_usage, processes

    def collect_data(
        self, args: Optional[ProcessCollectorArgs] = None
    ) -> Tuple[TaskResult, Optional[ProcessDataModel]]:
        """Read aggregate CPU usage and top processes from Linux ``/proc``.

        Args:
            args (Optional[ProcessCollectorArgs], optional): ``top_n_process`` and
                ``sample_interval_seconds``. Defaults to ``ProcessCollectorArgs()``.

        Returns:
            tuple containing the task result and ``ProcessDataModel`` or None if collection failed.
        """
        if args is None:
            args = ProcessCollectorArgs()

        sample_interval_seconds = args.sample_interval_seconds
        if sample_interval_seconds <= 0:
            sample_interval_seconds = 1.0

        process_data = ProcessDataModel()

        cpu_usage, processes = self._collect_procfs_cpu(args.top_n_process, sample_interval_seconds)
        if cpu_usage is not None:
            process_data.cpu_usage = cpu_usage
            process_data.processes = processes

        if process_data.cpu_usage is not None:
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
