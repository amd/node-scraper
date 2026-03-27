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
from unittest.mock import MagicMock, patch

import pytest

from nodescraper.enums.eventcategory import EventCategory
from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.interfaces.task import SystemCompatibilityError
from nodescraper.models.systeminfo import OSFamily
from nodescraper.plugins.inband.process.process_collector import (
    ProcessCollector,
    _global_non_idle_percent,
    _parse_aggregate_cpu_from_proc_stat,
    _parse_comm_dump,
    _parse_proc_pid_stat,
    _parse_proc_stat_dump,
    _top_process_cpu_shares,
)
from nodescraper.plugins.inband.process.processdata import ProcessDataModel

PROC_STAT_1 = (
    "cpu  100 0 0 900 0 0 0 0 0 0\n"
    "cpu0  55 0 0 495 0 0 0 0 0 0\n"
    "cpu1  45 0 0 405 0 0 0 0 0 0\n"
)
PROC_STAT_2 = (
    "cpu  200 0 0 1800 0 0 0 0 0 0\n"
    "cpu0 110 0 0 990 0 0 0 0 0 0\n"
    "cpu1  90 0 0 810 0 0 0 0 0 0\n"
)

DUMP_1 = (
    "__SAMPLER__:99999\n"
    "1000|1000 (ksoftirqd/0) S 0 0 0 0 -1 69238848 0 0 0 0 5000 6000\n"
    "1|1 (systemd) S 0 1 1 0 -1 4194560 100 200 300 400 5000 6000\n"
)

DUMP_2 = (
    "__SAMPLER__:99999\n"
    "1000|1000 (ksoftirqd/0) S 0 0 0 0 -1 69238848 0 0 0 0 5100 6000\n"
    "1|1 (systemd) S 0 1 1 0 -1 4194560 100 200 300 400 5000 6000\n"
)


@pytest.fixture
def collector(system_info, conn_mock):
    return ProcessCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


def _command_runner():
    proc_stat_calls = 0
    dump_calls = 0

    def run_command(command, sudo=False, timeout=300, strip=True):
        nonlocal proc_stat_calls, dump_calls
        if command == "cat /proc/stat":
            proc_stat_calls += 1
            body = PROC_STAT_1 if proc_stat_calls == 1 else PROC_STAT_2
            return MagicMock(exit_code=0, stdout=body, stderr="", command=command)
        if "for f in /proc/" in command and "__SAMPLER__" in command:
            dump_calls += 1
            body = DUMP_1 if dump_calls == 1 else DUMP_2
            return MagicMock(exit_code=0, stdout=body, stderr="", command=command)
        if "cat /proc/$p/comm" in command:
            return MagicMock(
                exit_code=0,
                stdout="1000:ksoftirqd/0\n1:systemd\n",
                stderr="",
                command=command,
            )
        raise AssertionError(f"unexpected command: {command!r}")

    return run_command


@patch("nodescraper.plugins.inband.process.process_collector.time.sleep")
def test_run_linux_procfs(mock_sleep, collector, conn_mock):
    collector.system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.side_effect = _command_runner()

    result, data = collector.collect_data()
    assert result.status == ExecutionStatus.OK
    assert data == ProcessDataModel(
        cpu_usage=10.0,
        processes=[
            ("ksoftirqd/0", "10.0"),
            ("systemd", "0.0"),
        ],
    )


def test_unsupported_platform(system_info, conn_mock):
    system_info.os_family = OSFamily.WINDOWS
    with pytest.raises(SystemCompatibilityError):
        ProcessCollector(
            system_info=system_info,
            system_interaction_level=SystemInteractionLevel.PASSIVE,
            connection=conn_mock,
        )


@patch("nodescraper.plugins.inband.process.process_collector.time.sleep")
def test_exit_failure_procfs(mock_sleep, collector, conn_mock):
    collector.system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.side_effect = [
        MagicMock(exit_code=1, stdout="", stderr="no proc", command="cat /proc/stat"),
    ]

    result, data = collector.collect_data()
    assert result.status == ExecutionStatus.EXECUTION_FAILURE
    assert data is None


@patch("nodescraper.plugins.inband.process.process_collector.time.sleep")
def test_invalid_proc_stat_logs_os_event(mock_sleep, collector, conn_mock):
    collector.system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.side_effect = [
        MagicMock(
            exit_code=0, stdout="not a valid proc_stat\n", stderr="", command="cat /proc/stat"
        ),
        MagicMock(exit_code=0, stdout="__SAMPLER__:1\n", stderr="", command="stat-dump-1"),
        MagicMock(exit_code=0, stdout="still bad\n", stderr="", command="cat /proc/stat"),
        MagicMock(exit_code=0, stdout="__SAMPLER__:1\n", stderr="", command="stat-dump-2"),
    ]
    with patch.object(collector, "_log_event") as mock_log:
        result, data = collector.collect_data()

    assert result.status == ExecutionStatus.EXECUTION_FAILURE
    assert data is None
    os_parse_logs = [
        c
        for c in mock_log.call_args_list
        if c.kwargs.get("category") == EventCategory.OS
        and "aggregate cpu" in (c.kwargs.get("description") or "")
    ]
    assert os_parse_logs, "Expected OS event for unparseable /proc/stat aggregate cpu line"


class TestProcessCollectorProcfsParsing:
    def test_parse_aggregate_cpu_from_proc_stat(self):
        text = "cpu0 1 2 3 4 5 6 7 8\n" "cpu 100 0 0 900 0 0 0 0 0 0\n"
        assert _parse_aggregate_cpu_from_proc_stat(text) == (1000, 900)

    def test_parse_aggregate_cpu_from_proc_stat_invalid(self):
        assert _parse_aggregate_cpu_from_proc_stat("cpu 1 2\n") is None
        assert _parse_aggregate_cpu_from_proc_stat("no aggregate line\n") is None

    def test_global_non_idle_percent(self):
        t1, i1 = 1000, 900
        t2, i2 = 2000, 1800
        assert _global_non_idle_percent(t1, i1, t2, i2) == 10.0

    def test_parse_proc_pid_stat(self):
        stat_line = DUMP_1.splitlines()[1].split("|", 1)[1]
        assert _parse_proc_pid_stat(stat_line) == (1000, 11000)

    def test_parse_proc_stat_dump(self):
        dump = "__SAMPLER__:12345\n" + "\n".join(DUMP_1.splitlines()[1:])
        jf, excl = _parse_proc_stat_dump(dump)
        assert excl == {12345}
        assert jf[1000] == 11000
        assert jf[1] == 11000

    def test_top_process_cpu_shares(self):
        s1 = {1: 100, 2: 200}
        s2 = {1: 100, 2: 400}
        top = _top_process_cpu_shares(s1, s2, total_delta=1000, top_n=2, exclude_pids=set())
        assert top[0][0] == 2
        assert top[0][1] == 20.0
        assert top[1][1] == 0.0

    def test_parse_comm_dump(self):
        m = _parse_comm_dump("1000:ksoftirqd/0\n1:systemd\n")
        assert m[1000] == "ksoftirqd/0"
        assert m[1] == "systemd"
