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
import logging
import time
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from nodescraper.enums.eventcategory import EventCategory
from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.interfaces.task import SystemCompatibilityError
from nodescraper.models.systeminfo import OSFamily
from nodescraper.plugins.inband.process import (
    process_collector as process_collector_module,
)
from nodescraper.plugins.inband.process.collector_args import ProcessCollectorArgs
from nodescraper.plugins.inband.process.process_collector import ProcessCollector
from nodescraper.plugins.inband.process.processdata import ProcessDataModel

PROC_STAT_1 = "cpu 100 0 0 900 0 0 0 0 0 0\n"
PROC_STAT_2 = "cpu 200 0 0 1800 0 0 0 0 0 0\n"
PROC_DUMP_1 = (
    "__SAMPLER__:99999\n"
    "1000|1000 (worker) S 0 0 0 0 -1 0 0 0 0 0 5000 6000\n"
    "1|1 (systemd) S 0 0 0 0 -1 0 0 0 0 0 5000 6000\n"
)
PROC_DUMP_2 = (
    "__SAMPLER__:99999\n"
    "1000|1000 (worker) S 0 0 0 0 -1 0 0 0 0 0 5100 6000\n"
    "1|1 (systemd) S 0 0 0 0 -1 0 0 0 0 0 5000 6000\n"
)


@pytest.fixture
def collector(system_info, conn_mock):
    return ProcessCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


def test_process_read_event_uses_shared_category():
    assert EventCategory.PROCESS_READ.value == "PROCESS_READ"


def test_parse_aggregate_cpu_from_proc_stat():
    proc_stat = "cpu0 1 2 3 4 5 6 7 8\ncpu 100 0 0 900 10 0 0 0 0 0\n"

    assert process_collector_module._parse_aggregate_cpu_from_proc_stat(proc_stat) == (1010, 910)


def test_parse_aggregate_cpu_excludes_guest_fields():
    proc_stat = "cpu 100 20 30 800 10 5 4 1 40 10\n"

    assert process_collector_module._parse_aggregate_cpu_from_proc_stat(proc_stat) == (970, 810)


def test_collector_args_reject_nonpositive_sample_interval():
    with pytest.raises(ValidationError):
        ProcessCollectorArgs(sample_interval_seconds=0)


def test_global_non_idle_percent_uses_jiffy_deltas():
    assert process_collector_module._global_non_idle_percent(1000, 900, 2000, 1800) == 10.0


def test_parse_proc_pid_stat_handles_process_names_with_spaces():
    stat_line = "1000 (worker process) S 0 0 0 0 -1 0 0 0 0 0 5000 6000"

    assert process_collector_module._parse_proc_pid_stat(stat_line) == (1000, 11000)


def test_parse_proc_pid_stat_handles_closing_parenthesis_in_process_name():
    stat_line = "1000 (worker) process) S 0 0 0 0 -1 0 0 0 0 0 5000 6000"

    assert process_collector_module._parse_proc_pid_stat(stat_line) == (1000, 11000)


def test_parse_proc_stat_dump_returns_jiffies_and_sampler_pid():
    dump = (
        "__SAMPLER__:99999\n"
        "1000|1000 (worker process) S 0 0 0 0 -1 0 0 0 0 0 5000 6000\n"
        "invalid line\n"
    )

    assert process_collector_module._parse_proc_stat_dump(dump) == ({1000: 11000}, {99999})


def test_top_process_cpu_shares_ranks_deltas_and_excludes_sampler():
    first_sample = {1: 100, 2: 200, 99: 0}
    second_sample = {1: 150, 2: 400, 99: 500}

    assert process_collector_module._top_process_cpu_shares(
        first_sample,
        second_sample,
        total_delta=1000,
        top_n=2,
        exclude_pids={99},
    ) == [(2, 20.0), (1, 5.0)]


def test_top_process_cpu_shares_excludes_processes_missing_from_current_sample():
    assert process_collector_module._top_process_cpu_shares(
        sample1={1: 100, 2: 200},
        sample2={2: 400},
        total_delta=1000,
        top_n=2,
        exclude_pids=set(),
    ) == [(2, 20.0)]


def test_parse_comm_dump_maps_process_names_by_pid():
    assert process_collector_module._parse_comm_dump("1000:worker\n1:systemd\ninvalid\n") == {
        1000: "worker",
        1: "systemd",
    }


def test_run_linux_collects_cpu_and_processes_from_procfs(collector, conn_mock, monkeypatch):
    proc_stat_calls = 0
    proc_dump_calls = 0

    def run_command(command, **_kwargs):
        nonlocal proc_stat_calls, proc_dump_calls
        if command == "cat /proc/stat":
            proc_stat_calls += 1
            stdout = PROC_STAT_1 if proc_stat_calls == 1 else PROC_STAT_2
        elif "for f in /proc/" in command and "__SAMPLER__" in command:
            proc_dump_calls += 1
            stdout = PROC_DUMP_1 if proc_dump_calls == 1 else PROC_DUMP_2
        elif "cat /proc/$p/comm" in command:
            stdout = "1000:\n1:systemd\n"
        else:
            raise AssertionError(f"unexpected command: {command}")
        return MagicMock(exit_code=0, stdout=stdout, stderr="", command=command)

    conn_mock.run_command.side_effect = run_command
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    result, data = collector.collect_data(
        ProcessCollectorArgs(top_n_process=2, sample_interval_seconds=0.01)
    )

    assert result.status == ExecutionStatus.OK
    assert data == ProcessDataModel(
        cpu_usage=10.0,
        processes=[("pid_1000", "10.0"), ("systemd", "0.0")],
    )
    assert all("__SAMPLER__" not in artifact.command for artifact in result.artifacts)


def test_unsupported_platform(system_info, conn_mock):
    system_info.os_family = OSFamily.WINDOWS
    with pytest.raises(SystemCompatibilityError):
        ProcessCollector(
            system_info=system_info,
            system_interaction_level=SystemInteractionLevel.PASSIVE,
            connection=conn_mock,
        )


def test_exit_failure(collector, conn_mock):
    collector.system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.side_effect = [
        MagicMock(exit_code=1, stdout="", stderr=""),
        MagicMock(exit_code=0, stdout="", stderr=""),
        MagicMock(exit_code=0, stdout="", stderr=""),
    ]

    result, data = collector.collect_data()
    assert result.status == ExecutionStatus.EXECUTION_FAILURE
    assert data is None


@pytest.mark.parametrize(
    ("failure_index", "expected_warning"),
    [
        (0, "first aggregate CPU sample"),
        (1, "first process CPU sample"),
        (2, "second aggregate CPU sample"),
        (3, "second process CPU sample"),
    ],
)
def test_procfs_command_failure_logs_warning(
    collector, conn_mock, monkeypatch, caplog, failure_index, expected_warning
):
    responses = [
        MagicMock(exit_code=0, stdout=PROC_STAT_1, stderr=""),
        MagicMock(exit_code=0, stdout=PROC_DUMP_1, stderr=""),
        MagicMock(exit_code=0, stdout=PROC_STAT_2, stderr=""),
        MagicMock(exit_code=0, stdout=PROC_DUMP_2, stderr=""),
    ]
    responses[failure_index].exit_code = 1
    conn_mock.run_command.side_effect = responses
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    with caplog.at_level(logging.WARNING):
        result, data = collector.collect_data()

    assert result.status == ExecutionStatus.EXECUTION_FAILURE
    assert data is None
    assert expected_warning in caplog.text


def test_invalid_proc_stat_returns_failure_and_logs_os_event(collector, conn_mock, monkeypatch):
    conn_mock.run_command.side_effect = [
        MagicMock(exit_code=0, stdout="not proc stat\n", stderr=""),
        MagicMock(exit_code=0, stdout="__SAMPLER__:99999\n", stderr=""),
        MagicMock(exit_code=0, stdout=PROC_STAT_2, stderr=""),
        MagicMock(exit_code=0, stdout="__SAMPLER__:99999\n", stderr=""),
    ]
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)

    result, data = collector.collect_data(ProcessCollectorArgs(sample_interval_seconds=0.01))

    assert result.status == ExecutionStatus.EXECUTION_FAILURE
    assert data is None
    assert any(event.category == EventCategory.OS.value for event in result.events)
