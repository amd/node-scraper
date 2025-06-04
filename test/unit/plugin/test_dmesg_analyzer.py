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
import datetime

from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.plugins.inband.dmesg.analyzer_args import DmesgAnalyzerArgs
from nodescraper.plugins.inband.dmesg.dmesg_analyzer import DmesgAnalyzer
from nodescraper.plugins.inband.dmesg.dmesgdata import DmesgData


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


def test_unknown_errors(system_info):
    dmesg_data = DmesgData(
        dmesg_content=(
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
    )

    analyzer = DmesgAnalyzer(system_info=system_info)

    exp_res = [
        {"match": "oom_kill_process", "desc": "Out of memory error", "count": 1},
        {"match": "qcm fence wait loop timeout expired", "desc": "QCM fence timeout", "count": 1},
        {
            "match": "amdgpu: Failed to disallow cf state",
            "desc": "Failed to disallow cf state",
            "count": 1,
        },
        {
            "match": ": Fatal error during GPU init",
            "desc": "Fatal error during GPU init",
            "count": 1,
        },
        {"match": "unknown error", "desc": "Unknown dmesg error", "count": 3},
        {"match": "unknown crit", "desc": "Unknown dmesg error", "count": 1},
        {"match": "unknown emerg", "desc": "Unknown dmesg error", "count": 1},
        {"match": "unknown alert", "desc": "Unknown dmesg error", "count": 1},
    ]

    res = analyzer.analyze_data(dmesg_data)

    assert res.status == ExecutionStatus.ERROR
    assert len(res.events) == 8

    for i, event in enumerate(res.events):
        assert event.description == exp_res[i]["desc"]
        assert event.data["match_content"] == exp_res[i]["match"]
        assert event.data["count"] == exp_res[i]["count"]

    res = analyzer.analyze_data(
        dmesg_data, args=DmesgAnalyzerArgs(check_unknown_dmesg_errors=False)
    )
    assert res.status == ExecutionStatus.ERROR
    assert len(res.events) == 4


def test_exclude_category(system_info):
    dmesg_data = DmesgData(
        dmesg_content=(
            "kern  :err   : 2024-10-07T10:17:15,145363-04:00 oom_kill_process\n"
            "kern  :err   : 2024-10-07T10:17:15,145363-04:00 amdgpu: qcm fence wait loop timeout expired\n"
            "kern  :err   : 2024-10-07T10:17:15,145363-04:00 amdgpu: Fatal error during GPU init\n"
            "kern  :err   : 2024-10-07T10:17:15,145363-04:00 amdgpu 0000:c1:00.0: amdgpu: socket: 4, die: 0 1 correctable hardware errors detected in total in gfx block, no user action is needed.\n"
            "kern  :err   : 2024-10-07T10:17:15,145363-04:00 amdgpu: Failed to disallow cf state\n"
        )
    )

    analyzer = DmesgAnalyzer(
        system_info=system_info,
    )

    res = analyzer.analyze_data(dmesg_data, args=DmesgAnalyzerArgs(exclude_category={"RAS"}))
    assert res.status == ExecutionStatus.ERROR
    assert len(res.events) == 4
    for event in res.events:
        assert event.category != "RAS"
