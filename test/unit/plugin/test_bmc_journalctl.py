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
"""Tests for JournalctlPlugin collector and analyzer."""

import json
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import MagicMock

import paramiko
import pytest
from pydantic import ValidationError

from nodescraper.connection.inband.inband import CommandArtifact
from nodescraper.connection.oob_ssh.amc_manager import AmcRemoteShell
from nodescraper.enums import EventPriority, ExecutionStatus
from nodescraper.plugins.ooband.bmc_journalctl import (
    JournalctlAnalyzer,
    JournalctlAnalyzerArgs,
    JournalctlCollector,
    JournalctlCollectorArgs,
    JournalctlData,
    JournalctlEntry,
    JournalctlMode,
)


def _journal_record(
    message: str = "test message",
    priority: int = 6,
    identifier: str = "bmcweb",
    timestamp_us: Optional[int] = None,
    unit: Optional[str] = None,
) -> str:
    record = {
        "MESSAGE": message,
        "PRIORITY": str(priority),
        "SYSLOG_IDENTIFIER": identifier,
    }
    if timestamp_us is not None:
        record["__REALTIME_TIMESTAMP"] = str(timestamp_us)
    if unit is not None:
        record["_SYSTEMD_UNIT"] = unit
    return json.dumps(record)


def _make_output(*records: str) -> str:
    return "\n".join(records) + "\n"


def _conn_mock(stdout: str = "") -> MagicMock:
    conn = MagicMock()
    conn.run_command.return_value = CommandArtifact(
        command="journalctl", stdout=stdout, stderr="", exit_code=0
    )
    return conn


def _collect(stdout: str, system_info, **args):
    conn = _conn_mock(stdout)
    collector = JournalctlCollector(system_info=system_info, connection=conn)
    result, data = collector.collect_data(JournalctlCollectorArgs(**args))
    commands = [str(c.args[0]) for c in conn.run_command.call_args_list]
    return result, data, commands


def test_amc_remote_shell_uses_warning_policy():
    assert AmcRemoteShell.host_key_policy is paramiko.WarningPolicy


def test_entry_parses_microsecond_timestamp():
    ts_us = 1767225600_000000
    entry = JournalctlEntry(**{"__REALTIME_TIMESTAMP": str(ts_us), "MESSAGE": "boot"})
    assert entry.timestamp == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert entry.message == "boot"


def test_entry_parses_iso_timestamp_round_trip():
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    data = JournalctlData(entries=[JournalctlEntry(timestamp=timestamp)])

    restored = JournalctlData.model_validate_json(data.model_dump_json())

    assert restored.entries[0].timestamp == timestamp


def test_entry_handles_byte_array_message():
    entry = JournalctlEntry(**{"MESSAGE": [72, 101, 108, 108, 111]})
    assert entry.message == "Hello"


def test_entry_handles_repeated_message_values():
    entry = JournalctlEntry(**{"MESSAGE": ["first", "second"]})
    assert entry.message == "first second"


def test_entry_handles_none_message():
    entry = JournalctlEntry(**{"MESSAGE": None})
    assert entry.message == ""


def test_entry_coerces_string_priority():
    entry = JournalctlEntry(**{"PRIORITY": "3", "MESSAGE": "err"})
    assert entry.priority == 3


def test_entry_equality_and_hash():
    a = JournalctlEntry(message="fail", priority=3, syslog_identifier="kernel")
    b = JournalctlEntry(message="fail", priority=3, syslog_identifier="kernel")
    c = JournalctlEntry(message="fail", priority=4, syslog_identifier="kernel")
    assert a == b
    assert hash(a) == hash(b)
    assert a != c


def test_default_mode_is_last_lines():
    args = JournalctlCollectorArgs()
    assert args.mode == JournalctlMode.LAST_LINES


def test_line_range_rejects_reversed():
    with pytest.raises(ValidationError):
        JournalctlCollectorArgs(mode="line_range", line_start=10, line_end=5)


def test_since_mode_requires_collect_since():
    with pytest.raises(ValidationError):
        JournalctlCollectorArgs(mode="since")


def test_unit_mode_requires_unit():
    with pytest.raises(ValidationError):
        JournalctlCollectorArgs(mode="unit")


def test_last_lines_default(system_info):
    output = _make_output(
        _journal_record("msg1", 6, "kernel"),
        _journal_record("msg2", 3, "bmcweb"),
    )
    result, data, commands = _collect(output, system_info)

    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert len(data.entries) == 2
    assert data.mode == "last_lines"
    assert "-n " in commands[0]
    assert "tail -n " in commands[0]
    assert "pipefail" in commands[0]
    assert "-p " not in commands[0]


def test_all_mode(system_info):
    output = _make_output(_journal_record())
    result, data, _ = _collect(output, system_info, mode="all")

    assert result.status == ExecutionStatus.OK
    assert data.mode == "all"


def test_unit_mode(system_info):
    output = _make_output(_journal_record("pldmd running", 6, "pldmd", unit="pldmd.service"))
    _, data, commands = _collect(output, system_info, mode="unit", unit="pldmd.service")

    assert data.entries[0].message == "pldmd running"
    assert "-u " in commands[0]
    assert "-n " in commands[0]


def test_since_mode(system_info):
    output = _make_output(_journal_record())
    _, _, commands = _collect(
        output, system_info, mode="since", collect_since="2026-01-01T00:00:00+00:00"
    )

    assert "--since " in commands[0]


def test_boot_mode(system_info):
    boot_output = " 0 abc123def456abc123def456abc123de Mon 2026-01-01\n"
    record_output = _make_output(_journal_record("boot entry"))

    conn = MagicMock()
    call_count = [0]

    def side_effect(cmd, timeout=30):
        call_count[0] += 1
        if call_count[0] == 1:
            return CommandArtifact(command=cmd, stdout=boot_output, stderr="", exit_code=0)
        return CommandArtifact(command=cmd, stdout=record_output, stderr="", exit_code=0)

    conn.run_command.side_effect = side_effect
    collector = JournalctlCollector(system_info=system_info, connection=conn)
    result, data = collector.collect_data(JournalctlCollectorArgs(mode="boot", boots=1))

    assert result.status == ExecutionStatus.OK
    assert len(data.entries) == 1


def test_boot_mode_enforces_global_entry_limit(system_info):
    boot_ids = ["a" * 32, "b" * 32, "c" * 32]
    boot_output = "\n".join(
        f" {i} {boot_id} Mon 2026-01-0{i + 1}" for i, boot_id in enumerate(boot_ids)
    )
    conn = MagicMock()
    call_count = [0]

    def side_effect(cmd, timeout=30):
        call_count[0] += 1
        if call_count[0] == 1:
            return CommandArtifact(command=cmd, stdout=boot_output, stderr="", exit_code=0)
        if f"-b {boot_ids[2]}" in cmd:
            output = _make_output(_journal_record("new boot one"), _journal_record("new boot two"))
        else:
            output = _make_output(_journal_record("middle boot entry"))
        return CommandArtifact(command=cmd, stdout=output, stderr="", exit_code=0)

    conn.run_command.side_effect = side_effect
    collector = JournalctlCollector(system_info=system_info, connection=conn)
    result, data = collector.collect_data(
        JournalctlCollectorArgs(mode="boot", boots=3, max_entries=3)
    )

    assert result.status == ExecutionStatus.OK
    assert len(data.entries) == 3
    assert data.truncated is True
    assert conn.run_command.call_count == 3
    assert "tail -n 1" in conn.run_command.call_args_list[2].args[0]
    assert [entry.message for entry in data.entries] == [
        "middle boot entry",
        "new boot one",
        "new boot two",
    ]


def test_skips_non_json_lines(system_info):
    output = "not json\n" + _make_output(_journal_record())
    result, data, _ = _collect(output, system_info, mode="all")

    assert len(data.entries) == 1
    assert any("Skipped 1" in e.description for e in result.events)


def test_strips_ansi_escapes(system_info):
    record = _journal_record("clean message")
    output = f"\x1b[0m{record}\n"
    _, data, _ = _collect(output, system_info, mode="all")

    assert data.entries[0].message == "clean message"


def test_truncation_warning(system_info):
    records = [_journal_record(f"msg{i}") for i in range(5)]
    output = _make_output(*records)
    result, data, _ = _collect(output, system_info, mode="all", max_entries=5)

    assert data.truncated is True
    assert any("ceiling" in e.description for e in result.events)


def test_first_lines_keeps_the_oldest_entries(system_info):
    output = _make_output(_journal_record())
    _, _, commands = _collect(output, system_info, mode="first_lines", line_count=5)

    assert "head -n 5" in commands[0]
    assert "tail -n " not in commands[0]


def test_nonzero_exit_fails_collection(system_info):
    conn = _conn_mock(_make_output(_journal_record()))
    conn.run_command.return_value.exit_code = 124
    conn.run_command.return_value.stderr = "Command timed out"
    collector = JournalctlCollector(system_info=system_info, connection=conn)
    result, data = collector.collect_data(JournalctlCollectorArgs(mode="all"))

    assert result.status == ExecutionStatus.EXECUTION_FAILURE
    assert data is None
    assert any("failed" in event.description for event in result.events)


def test_boot_mode_caps_combined_entries(system_info):
    boot_output = (
        "-1 aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa Mon 2026-01-01\n"
        " 0 bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb Mon 2026-01-02\n"
    )
    records = _make_output(*[_journal_record(f"msg{i}") for i in range(3)])
    conn = MagicMock()

    def side_effect(cmd, timeout=30):
        if "list-boots" in cmd:
            return CommandArtifact(command=cmd, stdout=boot_output, stderr="", exit_code=0)
        return CommandArtifact(command=cmd, stdout=records, stderr="", exit_code=0)

    conn.run_command.side_effect = side_effect
    collector = JournalctlCollector(system_info=system_info, connection=conn)
    result, data = collector.collect_data(
        JournalctlCollectorArgs(mode="boot", boots=2, max_entries=4)
    )

    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert len(data.entries) == 4
    assert data.truncated is True
    assert conn.run_command.call_count == 3


def test_boot_mode_stops_when_the_ceiling_is_already_met(system_info):
    boot_output = (
        "-1 aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa Mon 2026-01-01\n"
        " 0 bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb Mon 2026-01-02\n"
    )
    records = _make_output(*[_journal_record(f"msg{i}") for i in range(2)])
    conn = MagicMock()

    def side_effect(cmd, timeout=30):
        if "list-boots" in cmd:
            return CommandArtifact(command=cmd, stdout=boot_output, stderr="", exit_code=0)
        return CommandArtifact(command=cmd, stdout=records, stderr="", exit_code=0)

    conn.run_command.side_effect = side_effect
    collector = JournalctlCollector(system_info=system_info, connection=conn)
    _, data = collector.collect_data(JournalctlCollectorArgs(mode="boot", boots=2, max_entries=2))

    assert data is not None
    assert len(data.entries) == 2
    assert data.truncated is True
    assert conn.run_command.call_count == 2


def test_ssh_failure_returns_none(system_info):
    conn = MagicMock()
    conn.run_command.side_effect = Exception("SSH timeout")
    collector = JournalctlCollector(system_info=system_info, connection=conn)
    result, data = collector.collect_data(JournalctlCollectorArgs(mode="all"))

    assert result.status == ExecutionStatus.EXECUTION_FAILURE
    assert data is None


def test_nonzero_command_exit_code_is_failure(system_info):
    conn = _conn_mock(_make_output(_journal_record()))
    conn.run_command.return_value.exit_code = 2
    conn.run_command.return_value.stderr = "invalid priority"
    collector = JournalctlCollector(system_info=system_info, connection=conn)

    result, data = collector.collect_data(JournalctlCollectorArgs(mode="all"))

    assert result.status == ExecutionStatus.EXECUTION_FAILURE
    assert data is None
    assert any("invalid priority" in str(event.data) for event in result.events)
    assert "set -o pipefail;" in conn.run_command.call_args.args[0]


def test_ceiling_sigpipe_is_accepted(system_info):
    output = _make_output(_journal_record("entry one"), _journal_record("entry two"))
    conn = _conn_mock(output)
    conn.run_command.return_value.exit_code = 141
    collector = JournalctlCollector(system_info=system_info, connection=conn)

    result, data = collector.collect_data(JournalctlCollectorArgs(mode="all", max_entries=2))

    assert result.status == ExecutionStatus.OK
    assert data.truncated is True
    assert len(data.entries) == 2


def test_sigpipe_before_entry_ceiling_is_failure(system_info):
    conn = _conn_mock(_make_output(_journal_record()))
    conn.run_command.return_value.exit_code = 141
    collector = JournalctlCollector(system_info=system_info, connection=conn)

    result, data = collector.collect_data(JournalctlCollectorArgs(mode="all", max_entries=2))

    assert result.status == ExecutionStatus.EXECUTION_FAILURE
    assert data is None


def test_first_lines_sigpipe_at_the_line_count_is_accepted(system_info):
    output = _make_output(*[_journal_record(f"msg{index}") for index in range(5)])
    conn = _conn_mock(output)
    conn.run_command.return_value.exit_code = 141
    collector = JournalctlCollector(system_info=system_info, connection=conn)

    result, data = collector.collect_data(
        JournalctlCollectorArgs(mode="first_lines", line_count=5, max_entries=50)
    )

    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert len(data.entries) == 5


def test_first_lines_sigpipe_below_the_line_count_is_failure(system_info):
    conn = _conn_mock(_make_output(_journal_record()))
    conn.run_command.return_value.exit_code = 141
    collector = JournalctlCollector(system_info=system_info, connection=conn)

    result, data = collector.collect_data(
        JournalctlCollectorArgs(mode="first_lines", line_count=5, max_entries=50)
    )

    assert result.status == ExecutionStatus.EXECUTION_FAILURE
    assert data is None


def test_line_range_sigpipe_at_the_range_size_is_accepted(system_info):
    output = _make_output(_journal_record("first"), _journal_record("second"))
    conn = _conn_mock(output)
    conn.run_command.return_value.exit_code = 141
    collector = JournalctlCollector(system_info=system_info, connection=conn)

    result, data = collector.collect_data(
        JournalctlCollectorArgs(mode="line_range", line_start=1, line_end=2, max_entries=50)
    )

    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert len(data.entries) == 2


def test_unit_mode_caps_combined_entries(system_info):
    older = _make_output(
        _journal_record("old-a", timestamp_us=1_000_000),
        _journal_record("old-b", timestamp_us=2_000_000),
    )
    newer = _make_output(
        _journal_record("new-a", timestamp_us=3_000_000),
        _journal_record("new-b", timestamp_us=4_000_000),
    )
    conn = MagicMock()

    def side_effect(cmd, timeout=30):
        output = older if "unit-a" in cmd else newer
        return CommandArtifact(command=cmd, stdout=output, stderr="", exit_code=0)

    conn.run_command.side_effect = side_effect
    collector = JournalctlCollector(system_info=system_info, connection=conn)
    result, data = collector.collect_data(
        JournalctlCollectorArgs(
            mode="unit",
            unit=["unit-a.service", "unit-b.service"],
            line_count=2,
            max_entries=2,
        )
    )

    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert data.truncated is True
    assert [entry.message for entry in data.entries] == ["new-a", "new-b"]


def test_empty_output(system_info):
    result, data, _ = _collect("", system_info, mode="all")

    assert result.status == ExecutionStatus.OK
    assert data.entries == []


def _entry(
    message: str,
    priority: Optional[int],
    identifier: str = "kernel",
    ts: Optional[datetime] = None,
) -> JournalctlEntry:
    return JournalctlEntry(
        message=message, priority=priority, syslog_identifier=identifier, timestamp=ts
    )


def _analyze(entries, system_info, **args):
    data = JournalctlData(entries=entries, mode="all", command="journalctl")
    analyzer = JournalctlAnalyzer(system_info=system_info)
    return analyzer.analyze_data(data, JournalctlAnalyzerArgs(**args))


def test_error_priority_reported(system_info):
    result = _analyze([_entry("crash", 2)], system_info)

    assert len(result.events) == 1
    assert result.events[0].priority == EventPriority.ERROR


def test_warning_priority_reported(system_info):
    result = _analyze([_entry("low disk", 4)], system_info)

    assert len(result.events) == 1
    assert result.events[0].priority == EventPriority.WARNING


def test_info_priority_ignored(system_info):
    result = _analyze([_entry("normal", 6)], system_info)

    assert result.events == []


def test_none_priority_treated_as_error(system_info):
    result = _analyze([_entry("unknown", None)], system_info)

    assert len(result.events) == 1
    assert result.events[0].priority == EventPriority.ERROR


def test_grouping_collapses_duplicates(system_info):
    entries = [_entry("OOM", 3, "kernel") for _ in range(5)]
    result = _analyze(entries, system_info, group=True)

    assert len(result.events) == 1
    assert result.events[0].data["count"] == 5


def test_grouping_keeps_the_earliest_and_latest_timestamp(system_info):
    later = datetime(2026, 1, 10, tzinfo=timezone.utc)
    earlier = datetime(2026, 1, 1, tzinfo=timezone.utc)
    entries = [
        _entry("OOM", 3, "kernel", ts=later),
        _entry("OOM", 3, "kernel", ts=earlier),
    ]
    result = _analyze(entries, system_info, group=True)

    assert result.events[0].data["first_occurrence"] == earlier
    assert result.events[0].data["last_occurrence"] == later


def test_no_grouping_reports_each(system_info):
    entries = [_entry("OOM", 3, "kernel") for _ in range(3)]
    result = _analyze(entries, system_info, group=False)

    assert len(result.events) == 3


def test_time_range_filter(system_info):
    t1 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    t2 = datetime(2026, 1, 5, tzinfo=timezone.utc)
    t3 = datetime(2026, 1, 10, tzinfo=timezone.utc)
    entries = [
        _entry("old", 3, ts=t1),
        _entry("in range", 3, ts=t2),
        _entry("new", 3, ts=t3),
    ]
    result = _analyze(
        entries,
        system_info,
        analysis_range_start="2026-01-03T00:00:00+00:00",
        analysis_range_end="2026-01-07T00:00:00+00:00",
        group=False,
    )

    assert len(result.events) == 1
    assert result.events[0].data["Message"] == "in range"


def test_time_range_filter_interprets_naive_bounds_as_utc(system_info):
    entry = _entry("in range", 3, ts=datetime(2026, 1, 5, tzinfo=timezone.utc))
    result = _analyze(
        [entry],
        system_info,
        analysis_range_start="2026-01-03T00:00:00",
        analysis_range_end="2026-01-07T00:00:00",
        group=False,
    )

    assert len(result.events) == 1


def test_undated_entries_always_analyzed(system_info):
    entries = [_entry("no timestamp", 3, ts=None)]
    result = _analyze(entries, system_info, analysis_range_start="2026-06-01T00:00:00+00:00")

    assert len(result.events) == 1


def test_message_excerpt_truncation(system_info):
    long_msg = "x" * 200
    result = _analyze([_entry(long_msg, 3)], system_info)

    assert "..." in result.events[0].description
    assert len(result.events[0].description) < 300
