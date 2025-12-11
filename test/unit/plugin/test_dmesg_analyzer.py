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

from nodescraper.enums.eventpriority import EventPriority
from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.plugins.inband.dmesg.analyzer_args import (
    CustomErrorPattern,
    DmesgAnalyzerArgs,
)
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


def test_page_fault(system_info):
    dmesg_data = DmesgData(
        dmesg_content=(
            "kern  :err   : 2025-01-01T00:00:00,000000+00:00 amdgpu 0000:03:00.0: amdgpu: [mmhub0] no-retry page fault (src_id:0 ring:0 vmid:0 pasid:0, for process pid 0 thread pid 0)\n"
            "kern  :err   : 2025-01-01T00:00:01,000000+00:00 amdgpu 0000:03:00.0: amdgpu:   test example 123\n"
            "kern  :err   : 2025-01-01T00:00:02,000000+00:00 amdgpu 0000:03:00.0: amdgpu:   test example 123\n"
            "kern  :err   : 2025-01-01T00:00:03,000000+00:00 amdgpu 0000:03:00.0: amdgpu: VM_L2_PROTECTION_FAULT_STATUS:0x00000000\n"
            "kern  :err   : 2025-01-01T00:00:04,000000+00:00 amdgpu 0000:03:00.0: amdgpu: 	 Faulty UTCL2 client ID: ABC123 (0x000)\n"
            "kern  :err   : 2025-01-01T00:00:05,000000+00:00 amdgpu 0000:03:00.0: amdgpu: 	 MORE_FAULTS: 0x0\n"
            "kern  :err   : 2025-01-01T00:00:06,000000+00:00 amdgpu 0000:03:00.0: amdgpu: 	 WALKER_ERROR: 0x0\n"
            "kern  :err   : 2025-01-01T00:00:07,000000+00:00 amdgpu 0000:03:00.0: amdgpu: 	 PERMISSION_FAULTS: 0x0\n"
            "kern  :err   : 2025-01-01T00:00:08,000000+00:00 amdgpu 0000:03:00.0: amdgpu: 	 MAPPING_ERROR: 0x0\n"
            "kern  :err   : 2025-01-01T00:00:09,000000+00:00 amdgpu 0000:03:00.0: amdgpu: 	 RW: 0x0\n"
            "kern  :info  : 2025-01-01T00:00:10,000000+00:00 TEST TEST\n"
            "kern  :err   : 2025-01-01T00:00:11,000000+00:00 amdgpu 0000:03:00.0: amdgpu: [gfxhub0] retry page fault (src_id:0 ring:0 vmid:0 pasid:0, for process pid 0 thread pid 0)\n"
            "kern  :err   : 2025-01-01T00:00:12,000000+00:00 amdgpu 0000:03:00.0: amdgpu:   test example 123\n"
            "kern  :err   : 2025-01-01T00:00:13,000000+00:00 amdgpu 0000:03:00.0: amdgpu:   test example 123\n"
            "kern  :err   : 2025-01-01T00:00:14,000000+00:00 amdgpu 0000:03:00.0: amdgpu: VM_L2_PROTECTION_FAULT_STATUS:0x00000000\n"
            "kern  :err   : 2025-01-01T00:00:15,000000+00:00 amdgpu 0000:03:00.0: amdgpu: 	 Faulty UTCL2 client ID: ABC123 (0x000)\n"
            "kern  :err   : 2025-01-01T00:00:16,000000+00:00 amdgpu 0000:03:00.0: amdgpu: 	 MORE_FAULTS: 0x0\n"
            "kern  :err   : 2025-01-01T00:00:17,000000+00:00 amdgpu 0000:03:00.0: amdgpu: 	 WALKER_ERROR: 0x0\n"
            "kern  :err   : 2025-01-01T00:00:18,000000+00:00 amdgpu 0000:03:00.0: amdgpu: 	 PERMISSION_FAULTS: 0x0\n"
            "kern  :err   : 2025-01-01T00:00:19,000000+00:00 amdgpu 0000:03:00.0: amdgpu: 	 MAPPING_ERROR: 0x0\n"
            "kern  :err   : 2025-01-01T00:00:20,000000+00:00 amdgpu 0000:03:00.0: amdgpu: 	 RW: 0x0\n"
            "kern  :info  : 2025-01-01T00:00:21,000000+00:00 TEST TEST\n"
            "kern  :err   : 2025-01-01T00:00:22,000000+00:00 amdgpu 0003:02:00.0: amdgpu:  [gfxhub0] retry page fault (swpekfwpo\n"
            "kern  :info  : 2025-01-01T00:00:23,000000+00:00 TEST TEST\n"
            "kern  :err   : 2025-01-01T00:00:24,000000+00:00 amdgpu 0000:f5:00.0: amdgpu: [mmhub0] no-retry page fault (src_id:0 ring:0 vmid:0 pasid:0, for process pid 0 thread pid 0)\n"
            "kern  :err   : 2025-01-01T00:00:25,000000+00:00 amdgpu 0000:f5:00.0: amdgpu:   test example 123\n"
            "kern  :err   : 2025-01-01T00:00:26,000000+00:00 amdgpu 0000:f5:00.0: amdgpu:   test example 123\n"
            "kern  :err   : 2025-01-01T00:00:27,000000+00:00 amdgpu 0000:f5:00.0: amdgpu:   test example 123\n"
            "kern  :err   : 2025-01-01T00:00:28,000000+00:00 amdgpu 0000:f5:00.0: amdgpu: VM_L2_PROTECTION_FAULT_STATUS:0x00000000\n"
            "kern  :err   : 2025-01-01T00:00:29,000000+00:00 amdgpu 0000:f5:00.0: amdgpu: 	 Faulty UTCL2 client ID: ABC123 (0x000)\n"
            "kern  :err   : 2025-01-01T00:00:30,000000+00:00 amdgpu 0000:f5:00.0: amdgpu: 	 MORE_FAULTS: 0x0\n"
            "kern  :err   : 2025-01-01T00:00:31,000000+00:00 amdgpu 0000:f5:00.0: amdgpu: 	 WALKER_ERROR: 0x0\n"
            "kern  :err   : 2025-01-01T00:00:32,000000+00:00 amdgpu 0000:f5:00.0: amdgpu: 	 PERMISSION_FAULTS: 0x0\n"
            "kern  :err   : 2025-01-01T00:00:33,000000+00:00 amdgpu 0000:f5:00.0: amdgpu: 	 MAPPING_ERROR: 0x0\n"
            "kern  :err   : 2025-01-01T00:00:34,000000+00:00 amdgpu 0000:f5:00.0: amdgpu: 	 RW: 0x0\n"
        )
    )

    analyzer = DmesgAnalyzer(
        system_info=system_info,
    )

    res = analyzer.analyze_data(dmesg_data)
    assert res.status == ExecutionStatus.ERROR
    assert len(res.events) == 4
    for event in res.events:
        assert event.priority == EventPriority.ERROR
        assert event.description == "amdgpu Page Fault"


def test_lnet_and_lustre_boot_errors_are_warning_events(system_info):
    dmesg_log = "\n".join(
        [
            "[  548.063411] LNetError: 2719:0:(o2iblnd.c:3327:kiblnd_startup()) ko2iblnd: No matching interfaces",
            "[  548.073737] LNetError: 105-4: Error -100 starting up LNI o2ib",
            "[Wed Jun 25 17:19:52 2025] LustreError: 2719:0:(events.c:639:ptlrpc_init_portals()) network initialisation failed",
        ]
    )

    analyzer = DmesgAnalyzer(
        system_info=system_info,
    )
    data = DmesgData(dmesg_content=dmesg_log)
    result = analyzer.analyze_data(data, DmesgAnalyzerArgs())

    by_msg = {e.description: e for e in result.events}

    m1 = "LNet: ko2iblnd has no matching interfaces"
    m2 = "LNet: Error starting up LNI"
    m3 = "Lustre: network initialisation failed"

    assert m1 in by_msg, f"Missing event: {m1}"
    assert m2 in by_msg, f"Missing event: {m2}"
    assert m3 in by_msg, f"Missing event: {m3}"

    for m in (m1, m2, m3):
        ev = by_msg[m]
        assert ev.priority == EventPriority.WARNING, f"{m} should be WARNING"


def test_aca(system_info):
    aca_data1 = DmesgData(
        dmesg_content=(
            "kern  :err   : 2025-01-01T10:17:15,145363-04:00 amdgpu 0000:0c:00.0: amdgpu: [Hardware error] Accelerator Check Architecture events logged\n"
            "kern  :err   : 2025-01-01T10:17:15,145363-04:00 amdgpu 0000:0c:00.0: amdgpu: [Hardware error] aca entry[00].STATUS=0x000000000000000f\n"
            "kern  :err   : 2025-01-01T10:17:15,145363-04:00 amdgpu 0000:0c:00.0: amdgpu: [Hardware error] aca entry[00].ADDR=0x0000000000000000\n"
            "kern  :err   : 2025-01-01T10:17:15,145363-04:00 amdgpu 0000:0c:00.0: amdgpu: [Hardware error] aca entry[00].MISC0=0x0000000000000000\n"
            "kern  :err   : 2025-01-01T10:17:15,145363-04:00 amdgpu 0000:0c:00.0: amdgpu: [Hardware error] aca entry[00].IPID=0x0000000000000000\n"
            "kern  :err   : 2025-01-01T10:17:15,145363-04:00 amdgpu 0000:0c:00.0: amdgpu: [Hardware error] aca entry[00].SYND=0x0000000000000000\n"
        )
    )

    aca_data2 = DmesgData(
        dmesg_content=(
            "kern  :err   : 2025-01-01T17:53:23,028841-06:00 amdgpu 0000:48:00.0: {1}[Hardware Error]: Accelerator Check Architecture events logged\n"
            "kern  :err   : 2025-01-01T17:53:23,028841-06:00 amdgpu 0000:48:00.0: {1}[Hardware Error]: ACA[01/01].CONTROL=0x000000000000000f\n"
            "kern  :err   : 2025-01-01T17:53:23,028841-06:00 amdgpu 0000:48:00.0: {1}[Hardware Error]: ACA[01/01].STATUS=0x0000000000000000\n"
            "kern  :err   : 2025-01-01T17:53:23,028841-06:00 amdgpu 0000:48:00.0: {1}[Hardware Error]: ACA[01/01].ADDR=0x0000000000000000\n"
            "kern  :err   : 2025-01-01T17:53:23,028841-06:00 amdgpu 0000:48:00.0: {1}[Hardware Error]: ACA[01/01].MISC=0x0000000000000000\n"
            "kern  :err   : 2025-01-01T17:53:23,028841-06:00 amdgpu 0000:48:00.0: {1}[Hardware Error]: ACA[01/01].CONFIG=0x0000000000000000\n"
            "kern  :err   : 2025-01-01T17:53:23,028841-06:00 amdgpu 0000:48:00.0: {1}[Hardware Error]: ACA[01/01].IPID=0x0000000000000000\n"
            "kern  :err   : 2025-01-01T17:53:23,028841-06:00 amdgpu 0000:48:00.0: {1}[Hardware Error]: ACA[01/01].SYND=0x0000000000000000\n"
            "kern  :err   : 2025-01-01T17:53:23,028841-06:00 amdgpu 0000:48:00.0: {1}[Hardware Error]: ACA[01/01].DESTAT=0x0000000000000000\n"
            "kern  :err   : 2025-01-01T17:53:23,028841-06:00 amdgpu 0000:48:00.0: {1}[Hardware Error]: ACA[01/01].DEADDR=0x0000000000000000\n"
            "kern  :err   : 2025-01-01T17:53:23,028841-06:00 amdgpu 0000:48:00.0: {1}[Hardware Error]: ACA[01/01].CONTROL_MASK=0x0000000000000000\n"
        )
    )

    analyzer = DmesgAnalyzer(
        system_info=system_info,
    )

    res = analyzer.analyze_data(aca_data1)
    assert res.status == ExecutionStatus.ERROR
    assert len(res.events) == 1
    assert res.events[0].description == "ACA Error"
    assert res.events[0].priority == EventPriority.ERROR

    res = analyzer.analyze_data(aca_data2)
    assert res.status == ExecutionStatus.ERROR
    assert len(res.events) == 1
    assert res.events[0].description == "ACA Error"
    assert res.events[0].priority == EventPriority.ERROR


def test_custom_error_patterns_basic(system_info):
    """Test basic custom error pattern functionality."""
    dmesg_data = DmesgData(
        dmesg_content=(
            "kern  :err   : 2024-10-07T10:17:15,145363-04:00 my_driver failed to initialize\n"
            "kern  :err   : 2024-10-07T10:17:16,145363-04:00 temperature reached critical threshold\n"
            "kern  :info  : 2024-10-07T10:17:17,145363-04:00 normal operation\n"
            "kern  :err   : 2024-10-07T10:17:18,145363-04:00 my_driver failed to start\n"
        )
    )

    analyzer = DmesgAnalyzer(system_info=system_info)

    custom_patterns = [
        CustomErrorPattern(
            pattern=r"my_driver.*failed",
            message="Custom driver failure",
            category="CUSTOM_DRIVER",
            priority="ERROR",
        ),
        CustomErrorPattern(
            pattern=r"temperature.*critical",
            message="Critical temperature",
            category="THERMAL",
            priority="CRITICAL",
        ),
    ]

    args = DmesgAnalyzerArgs(
        check_unknown_dmesg_errors=False, custom_error_patterns=custom_patterns
    )

    result = analyzer.analyze_data(dmesg_data, args)

    assert result.status == ExecutionStatus.ERROR
    assert len(result.events) == 2

    driver_events = [e for e in result.events if e.description == "Custom driver failure"]
    assert len(driver_events) == 1
    assert driver_events[0].category == "CUSTOM_DRIVER"
    assert driver_events[0].priority == EventPriority.ERROR
    assert driver_events[0].data["count"] == 2

    temp_events = [e for e in result.events if e.description == "Critical temperature"]
    assert len(temp_events) == 1
    assert temp_events[0].category == "THERMAL"
    assert temp_events[0].priority == EventPriority.CRITICAL
    assert temp_events[0].data["count"] == 1


def test_custom_error_patterns_with_unknown_errors(system_info):
    """Test custom error patterns combined with unknown error checking."""
    dmesg_data = DmesgData(
        dmesg_content=(
            "kern  :err   : 2024-10-07T10:17:15,145363-04:00 my_custom_error occurred\n"
            "kern  :err   : 2024-10-07T10:17:16,145363-04:00 some random unknown error\n"
        )
    )

    analyzer = DmesgAnalyzer(system_info=system_info)

    custom_patterns = [
        CustomErrorPattern(
            pattern=r"my_custom_error",
            message="My custom error detected",
            category="CUSTOM",
            priority="ERROR",
        )
    ]

    args = DmesgAnalyzerArgs(check_unknown_dmesg_errors=True, custom_error_patterns=custom_patterns)

    result = analyzer.analyze_data(dmesg_data, args)

    assert result.status == ExecutionStatus.ERROR
    assert len(result.events) == 3

    custom_events = [e for e in result.events if e.description == "My custom error detected"]
    assert len(custom_events) == 1
    assert custom_events[0].priority == EventPriority.ERROR

    unknown_events = [e for e in result.events if e.description == "Unknown dmesg error"]
    assert len(unknown_events) == 2
    assert unknown_events[0].priority == EventPriority.WARNING


def test_custom_error_patterns_invalid_regex(system_info):
    """Test handling of invalid regex patterns."""
    dmesg_data = DmesgData(
        dmesg_content="kern  :err   : 2024-10-07T10:17:15,145363-04:00 test error\n"
    )

    analyzer = DmesgAnalyzer(system_info=system_info)

    custom_patterns = [
        CustomErrorPattern(
            pattern=r"[invalid(regex",
            message="This should not work",
            category="INVALID",
            priority="ERROR",
        ),
        CustomErrorPattern(
            pattern=r"test error",
            message="Valid pattern",
            category="TEST",
            priority="ERROR",
        ),
    ]

    args = DmesgAnalyzerArgs(
        check_unknown_dmesg_errors=False, custom_error_patterns=custom_patterns
    )

    result = analyzer.analyze_data(dmesg_data, args)

    assert result.status == ExecutionStatus.ERROR

    valid_events = [e for e in result.events if e.description == "Valid pattern"]
    assert len(valid_events) == 1

    invalid_regex_warnings = [
        e for e in result.events if "Invalid custom error pattern regex" in e.description
    ]
    assert len(invalid_regex_warnings) == 1


def test_custom_error_patterns_priority_mapping(system_info):
    """Test that all priority levels are correctly mapped."""
    dmesg_data = DmesgData(
        dmesg_content=(
            "kern  :err   : 2024-10-07T10:17:15,145363-04:00 error_test\n"
            "kern  :err   : 2024-10-07T10:17:16,145363-04:00 warning_test\n"
            "kern  :err   : 2024-10-07T10:17:17,145363-04:00 critical_test\n"
            "kern  :err   : 2024-10-07T10:17:18,145363-04:00 info_test\n"
        )
    )

    analyzer = DmesgAnalyzer(system_info=system_info)

    custom_patterns = [
        CustomErrorPattern(
            pattern=r"error_test", message="Error priority", category="TEST", priority="ERROR"
        ),
        CustomErrorPattern(
            pattern=r"warning_test",
            message="Warning priority",
            category="TEST",
            priority="WARNING",
        ),
        CustomErrorPattern(
            pattern=r"critical_test",
            message="Critical priority",
            category="TEST",
            priority="CRITICAL",
        ),
        CustomErrorPattern(
            pattern=r"info_test", message="Info priority", category="TEST", priority="INFO"
        ),
    ]

    args = DmesgAnalyzerArgs(
        check_unknown_dmesg_errors=False, custom_error_patterns=custom_patterns
    )

    result = analyzer.analyze_data(dmesg_data, args)

    assert len(result.events) == 4

    error_event = [e for e in result.events if e.description == "Error priority"][0]
    assert error_event.priority == EventPriority.ERROR

    warning_event = [e for e in result.events if e.description == "Warning priority"][0]
    assert warning_event.priority == EventPriority.WARNING

    critical_event = [e for e in result.events if e.description == "Critical priority"][0]
    assert critical_event.priority == EventPriority.CRITICAL

    info_event = [e for e in result.events if e.description == "Info priority"][0]
    assert info_event.priority == EventPriority.INFO


def test_custom_error_patterns_empty_list(system_info):
    """Test that empty custom_error_patterns list doesn't cause issues."""
    dmesg_data = DmesgData(
        dmesg_content="kern  :err   : 2024-10-07T10:17:15,145363-04:00 oom_kill_process\n"
    )

    analyzer = DmesgAnalyzer(system_info=system_info)

    args = DmesgAnalyzerArgs(check_unknown_dmesg_errors=False, custom_error_patterns=[])

    result = analyzer.analyze_data(dmesg_data, args)

    assert result.status == ExecutionStatus.ERROR
    assert len(result.events) == 1
    assert result.events[0].description == "Out of memory error"
