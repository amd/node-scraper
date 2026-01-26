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
import types
from datetime import datetime

from nodescraper.enums import ExecutionStatus
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.plugins.inband.journal.analyzer_args import JournalAnalyzerArgs
from nodescraper.plugins.inband.journal.journal_analyzer import JournalAnalyzer
from nodescraper.plugins.inband.journal.journal_collector import JournalCollector
from nodescraper.plugins.inband.journal.journaldata import JournalData, JournalJsonEntry


class DummyRes:
    def __init__(self, command="", stdout="", exit_code=0, stderr=""):
        self.command = command
        self.stdout = stdout
        self.exit_code = exit_code
        self.stderr = stderr


def get_collector(monkeypatch, run_map, system_info, conn_mock):
    c = JournalCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.INTERACTIVE,
        connection=conn_mock,
    )
    c.result = types.SimpleNamespace(artifacts=[], message=None)
    c._events = []

    def _log_event(**kw):
        c._events.append(kw)

    def _run_sut_cmd(cmd, *args, **kwargs):
        return run_map(cmd, *args, **kwargs)

    monkeypatch.setattr(c, "_log_event", _log_event, raising=True)
    monkeypatch.setattr(c, "_run_sut_cmd", _run_sut_cmd, raising=True)

    return c


def test_collect_data_integration(monkeypatch, system_info, conn_mock):
    def run_map(cmd, **kwargs):
        return DummyRes(command=cmd, stdout='{"MESSAGE":"hello"}\n', exit_code=0)

    c = get_collector(monkeypatch, run_map, system_info, conn_mock)

    result, data = c.collect_data()
    assert isinstance(data, JournalData)

    assert data.journal_log == '{"MESSAGE":"hello"}\n'


def test_journal_filter():
    """Test filtering journal entries based on timestamp range."""
    journal_data = [
        {
            "TRANSPORT": "kernel",
            "MACHINE_ID": "dummy-machine-id-123456789abcdef",
            "HOSTNAME": "test-hostname-001",
            "SYSLOG_IDENTIFIER": "kernel",
            "CURSOR": "dummy-cursor-s1234;i=1000;b=dummy-boot-abc123;m=100;t=1000;x=dummy-x1",
            "SYSLOG_FACILITY": 0,
            "SOURCE_REALTIME_TIMESTAMP": None,
            "REALTIME_TIMESTAMP": "2025-02-23T21:03:46.685975",
            "PRIORITY": 1,
            "BOOT_ID": "dummy-boot-id-aabbccdd11223344",
            "SOURCE_MONOTONIC_TIMESTAMP": 0.0,
            "MONOTONIC_TIMESTAMP": 11418011.0,
            "MESSAGE": "Test kernel message - alert level",
        },
        {
            "TRANSPORT": "kernel",
            "MACHINE_ID": "dummy-machine-id-123456789abcdef",
            "HOSTNAME": "test-hostname-001",
            "SYSLOG_IDENTIFIER": "kernel",
            "CURSOR": "dummy-cursor-s1234;i=1001;b=dummy-boot-abc123;m=101;t=1001;x=dummy-x2",
            "SYSLOG_FACILITY": 0,
            "SOURCE_REALTIME_TIMESTAMP": None,
            "REALTIME_TIMESTAMP": "2025-02-23T21:03:46.686007",
            "PRIORITY": 5,
            "BOOT_ID": "dummy-boot-id-aabbccdd11223344",
            "SOURCE_MONOTONIC_TIMESTAMP": 0.0,
            "MONOTONIC_TIMESTAMP": 11418043.0,
            "MESSAGE": "Test kernel message - notice level",
        },
        {
            "TRANSPORT": "kernel",
            "MACHINE_ID": "dummy-machine-id-123456789abcdef",
            "HOSTNAME": "test-hostname-001",
            "SYSLOG_IDENTIFIER": "kernel",
            "CURSOR": "dummy-cursor-s1234;i=1002;b=dummy-boot-abc123;m=102;t=1002;x=dummy-x3",
            "SYSLOG_FACILITY": 0,
            "SOURCE_REALTIME_TIMESTAMP": None,
            "REALTIME_TIMESTAMP": "2025-02-23T21:03:46.686019",
            "PRIORITY": 2,
            "BOOT_ID": "dummy-boot-id-aabbccdd11223344",
            "SOURCE_MONOTONIC_TIMESTAMP": 0.0,
            "MONOTONIC_TIMESTAMP": 11418056.0,
            "MESSAGE": "Test kernel message - critical level",
        },
        {
            "TRANSPORT": "kernel",
            "MACHINE_ID": "dummy-machine-id-123456789abcdef",
            "HOSTNAME": "test-hostname-001",
            "SYSLOG_IDENTIFIER": "kernel",
            "CURSOR": "dummy-cursor-s1234;i=1003;b=dummy-boot-abc123;m=103;t=1003;x=dummy-x4",
            "SYSLOG_FACILITY": 0,
            "SOURCE_REALTIME_TIMESTAMP": None,
            "REALTIME_TIMESTAMP": "2025-02-23T21:03:46.686027",
            "PRIORITY": 7,
            "BOOT_ID": "dummy-boot-id-aabbccdd11223344",
            "SOURCE_MONOTONIC_TIMESTAMP": 0.0,
            "MONOTONIC_TIMESTAMP": 11418064.0,
            "MESSAGE": "Test kernel message - debug level",
        },
    ]

    journal_content_json = [JournalJsonEntry(**entry) for entry in journal_data]

    start_range = datetime.fromisoformat("2025-02-23T21:03:46.686006")
    end_range = datetime.fromisoformat("2025-02-23T21:03:46.686020")

    filtered_journal = JournalAnalyzer.filter_journal(journal_content_json, start_range, end_range)
    assert filtered_journal == [JournalJsonEntry(**entry) for entry in journal_data[1:3]]

    filtered_journal = JournalAnalyzer.filter_journal(journal_content_json, start_range, None)
    assert filtered_journal == [JournalJsonEntry(**entry) for entry in journal_data[1:]]

    filtered_journal = JournalAnalyzer.filter_journal(journal_content_json, None, end_range)
    assert filtered_journal == [JournalJsonEntry(**entry) for entry in journal_data[:3]]


def test_check_priority(system_info):
    """Test checking priority of journal entries."""
    journal_data_dict = {
        "journal_log": "",
        "journal_content_json": [
            {
                "TRANSPORT": "kernel",
                "MACHINE_ID": "dummy-machine-id-123456789abcdef",
                "HOSTNAME": "test-hostname-002",
                "SYSLOG_IDENTIFIER": "kernel",
                "CURSOR": "dummy-cursor-s2000;i=2000;b=dummy-boot-def456;m=200;t=2000;x=dummy-y1",
                "SYSLOG_FACILITY": 0,
                "SOURCE_REALTIME_TIMESTAMP": None,
                "REALTIME_TIMESTAMP": "2025-02-23T21:03:46.685975",
                "PRIORITY": 1,
                "BOOT_ID": "dummy-boot-id-11223344aabbccdd",
                "SOURCE_MONOTONIC_TIMESTAMP": 0.0,
                "MONOTONIC_TIMESTAMP": 11418011.0,
                "MESSAGE": "Test system alert message",
            },
            {
                "TRANSPORT": "kernel",
                "MACHINE_ID": "dummy-machine-id-123456789abcdef",
                "HOSTNAME": "test-hostname-002",
                "SYSLOG_IDENTIFIER": "kernel",
                "CURSOR": "dummy-cursor-s2000;i=2001;b=dummy-boot-def456;m=201;t=2001;x=dummy-y2",
                "SYSLOG_FACILITY": 0,
                "SOURCE_REALTIME_TIMESTAMP": None,
                "REALTIME_TIMESTAMP": "2025-02-23T21:03:46.686007",
                "PRIORITY": 5,
                "BOOT_ID": "dummy-boot-id-11223344aabbccdd",
                "SOURCE_MONOTONIC_TIMESTAMP": 0.0,
                "MONOTONIC_TIMESTAMP": 11418043.0,
                "MESSAGE": "Test notice level message",
            },
            {
                "TRANSPORT": "kernel",
                "MACHINE_ID": "dummy-machine-id-123456789abcdef",
                "HOSTNAME": "test-hostname-002",
                "SYSLOG_IDENTIFIER": "kernel",
                "CURSOR": "dummy-cursor-s2000;i=2002;b=dummy-boot-def456;m=202;t=2002;x=dummy-y3",
                "SYSLOG_FACILITY": 0,
                "SOURCE_REALTIME_TIMESTAMP": None,
                "REALTIME_TIMESTAMP": "2025-02-23T21:03:46.686019",
                "PRIORITY": 2,
                "BOOT_ID": "dummy-boot-id-11223344aabbccdd",
                "SOURCE_MONOTONIC_TIMESTAMP": 0.0,
                "MONOTONIC_TIMESTAMP": 11418056.0,
                "MESSAGE": "Test critical level message",
            },
            {
                "TRANSPORT": "kernel",
                "MACHINE_ID": "dummy-machine-id-123456789abcdef",
                "HOSTNAME": "test-hostname-002",
                "SYSLOG_IDENTIFIER": "kernel",
                "CURSOR": "dummy-cursor-s2000;i=2003;b=dummy-boot-def456;m=203;t=2003;x=dummy-y4",
                "SYSLOG_FACILITY": 0,
                "SOURCE_REALTIME_TIMESTAMP": None,
                "REALTIME_TIMESTAMP": "2025-02-23T21:03:46.686027",
                "PRIORITY": 7,
                "BOOT_ID": "dummy-boot-id-11223344aabbccdd",
                "SOURCE_MONOTONIC_TIMESTAMP": 0.0,
                "MONOTONIC_TIMESTAMP": 11418064.0,
                "MESSAGE": "Test debug level message",
            },
        ],
    }

    journal_data = JournalData(**journal_data_dict)
    analyzer = JournalAnalyzer(system_info=system_info)
    args = JournalAnalyzerArgs(check_priority=5)
    res = analyzer.analyze_data(data=journal_data, args=args)

    assert res.status == ExecutionStatus.ERROR
    assert len(res.events) == 3
