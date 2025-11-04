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
