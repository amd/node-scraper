import datetime

import pytest

from errorscraper.enums.eventpriority import EventPriority
from errorscraper.enums.executionstatus import ExecutionStatus
from errorscraper.plugins.inband.dmesg.analyzer_args import DmesgAnalyzerArgs
from errorscraper.plugins.inband.dmesg.dmesg_analyzer import DmesgAnalyzer
from errorscraper.plugins.inband.dmesg.dmesgdata import DmesgData


@pytest.fixture
def dmesg_data():
    dmesg = (
        "kern  :err   : 2024-10-07T10:17:15,145363-04:00 oom_kill_process\n"
        "kern  :err   : 2024-10-07T10:17:15,145363-04:00 amdgpu: qcm fence wait loop timeout expired\n"
        "kern  :err   : 2024-10-07T10:17:15,145363-04:00 unknown error\n"
        "kern  :err   : 2024-10-07T10:17:15,145363-04:00 unknown error\n"
        "kern  :err   : 2024-10-07T10:17:15,145363-04:00 unknown error\n"
        "kern  :err   : 2024-10-07T10:17:15,145363-04:00 amdgpu: Fatal error during GPU init\n"
        "kern  :crit   : 2024-10-07T10:17:15,145363-04:00 unknown crit\n"
        "kern  :emerg   : 2024-10-07T10:17:15,145363-04:00 unknown emerg\n"
        "kern  :alert   : 2024-10-07T10:17:15,145363-04:00 unknown alert\n"
        "kern  :err   : 2024-10-07T10:17:15,145363-04:00 amdgpu: Failed to disallow cf state\n"
    )
    return DmesgData(dmesg_content=dmesg)


def test_dmesg_filter():
    dmesg_log = (
        "kern  :info  : 2024-10-01T05:00:00,000000-05:00 test dmesg log1\n"
        "kern  :info  : 2024-10-01T06:00:00,000000-05:00 test dmesg log2\n"
        "kern  :info  : 2024-10-01T07:00:00,000000-05:00 test dmesg log3\n"
        "kern  :info  : 2024-10-01T08:00:00,000000-05:00 test dmesg log4\n"
        "kern  :info  : 2024-10-01T09:00:00,000000-05:00 test dmesg log5\n"
        "kern  :info  : 2024-10-01T10:00:00,000000-05:00 test dmesg log6\n"
        "kern  :info  : 2024-10-01T11:00:00,000000-05:00 test dmesg log7\n"
        "kern  :info  : 2024-10-01T12:00:00,000000-05:00 test dmesg log8"
    )

    start_range = datetime.datetime.fromisoformat("2024-10-01T07:30:00.000000-05:00")
    end_range = datetime.datetime.fromisoformat("2024-10-01T10:15:00.000000-05:00")

    filtered_dmesg = DmesgAnalyzer.filter_dmesg(dmesg_log, start_range, end_range)

    assert filtered_dmesg == (
        "kern  :info  : 2024-10-01T08:00:00,000000-05:00 test dmesg log4\n"
        "kern  :info  : 2024-10-01T09:00:00,000000-05:00 test dmesg log5\n"
        "kern  :info  : 2024-10-01T10:00:00,000000-05:00 test dmesg log6\n"
    )

    filtered_dmesg = DmesgAnalyzer.filter_dmesg(dmesg_log, start_range)

    assert filtered_dmesg == (
        "kern  :info  : 2024-10-01T08:00:00,000000-05:00 test dmesg log4\n"
        "kern  :info  : 2024-10-01T09:00:00,000000-05:00 test dmesg log5\n"
        "kern  :info  : 2024-10-01T10:00:00,000000-05:00 test dmesg log6\n"
        "kern  :info  : 2024-10-01T11:00:00,000000-05:00 test dmesg log7\n"
        "kern  :info  : 2024-10-01T12:00:00,000000-05:00 test dmesg log8\n"
    )

    filtered_dmesg = DmesgAnalyzer.filter_dmesg(dmesg_log, None, end_range)

    assert filtered_dmesg == (
        "kern  :info  : 2024-10-01T05:00:00,000000-05:00 test dmesg log1\n"
        "kern  :info  : 2024-10-01T06:00:00,000000-05:00 test dmesg log2\n"
        "kern  :info  : 2024-10-01T07:00:00,000000-05:00 test dmesg log3\n"
        "kern  :info  : 2024-10-01T08:00:00,000000-05:00 test dmesg log4\n"
        "kern  :info  : 2024-10-01T09:00:00,000000-05:00 test dmesg log5\n"
        "kern  :info  : 2024-10-01T10:00:00,000000-05:00 test dmesg log6\n"
    )


def test_unknown_errors(dmesg_data, system_info):
    analyzer = DmesgAnalyzer(system_info=system_info)

    # exp_res = [
    #    {"match": "oom_kill_process", "desc": "Out of memory error", "count": 1},
    #    {"match": "qcm fence wait loop timeout expired", "desc": "QCM fence timeout", "count": 1},
    #    {
    #        "match": "amdgpu: Failed to disallow cf state",
    #        "desc": "Failed to disallow cf state",
    #        "count": 1,
    #    },
    #    {
    #        "match": ": Fatal error during GPU init",
    #        "desc": "Fatal error during GPU init",
    #        "count": 1,
    #    },
    #    {"match": "unknown error", "desc": "Unknown dmesg error", "count": 3},
    #    {"match": "unknown crit", "desc": "Unknown dmesg error", "count": 1},
    #    {"match": "unknown emerg", "desc": "Unknown dmesg error", "count": 1},
    #    {"match": "unknown alert", "desc": "Unknown dmesg error", "count": 1},
    # ]

    res = analyzer.analyze_data({DmesgData: dmesg_data})

    assert res.status == ExecutionStatus.EXECUTION_FAILURE
    assert len(res.events) == 1
    for event in res.events:
        assert event.description == "Analyzer passed invalid data"

    # for i, event in enumerate(res.events):
    #    assert event.description == exp_res[i]["desc"]
    #    assert event.data["match_content"] == exp_res[i]["match"]
    #    assert event.data["count"] == exp_res[i]["count"]


def test_regex_match(dmesg_data, system_info):
    analyzer = DmesgAnalyzer(system_info=system_info)

    res = analyzer.analyze_data({DmesgData: dmesg_data})

    assert res.status == ExecutionStatus.EXECUTION_FAILURE
    # assert len(res.events) == len(DmesgAnalyzer.ERROR_REGEX)

    # for i, event in enumerate(res.events):
    #    assert event.priority == DmesgAnalyzer.ERROR_REGEX[i].event_priority
    #    assert event.description == DmesgAnalyzer.ERROR_REGEX[i].message


def test_page_fault(dmesg_data, system_info):
    analyzer = DmesgAnalyzer(system_info=system_info)

    res = analyzer.analyze_data({DmesgData: dmesg_data})

    assert res.status == ExecutionStatus.EXECUTION_FAILURE
    assert len(res.events) == 1

    for event in res.events:
        assert event.description == "Analyzer passed invalid data"
        assert event.priority == EventPriority.CRITICAL


def test_exclude_category(dmesg_data, system_info):
    analyzer = DmesgAnalyzer(system_info=system_info)

    args = DmesgAnalyzerArgs(exclude_category={"RAS"})
    res = analyzer.analyze_data({DmesgData: dmesg_data}, args)

    assert res.status == ExecutionStatus.EXECUTION_FAILURE
    assert len(res.events) == 1
    for event in res.events:
        assert event.category != "RAS"
