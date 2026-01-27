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
import pathlib

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


def test_ras_poison_errors(system_info):
    dmesg_data = DmesgData(
        dmesg_content=(
            "kern  :err   : 2024-11-24T17:53:23,028841-06:00 amdgpu 0000:68:00.0: {14}poison is consumed by client 12, kick off gpu reset flow\n"
            "kern  :err   : 2024-11-24T17:53:23,028841-06:00 amdgpu 0000:68:00.0: {15}Poison is created\n"
            "kern  :info  : 2024-11-24T17:53:24,028841-06:00 Normal log entry\n"
            "kern  :err   : 2024-11-24T17:53:25,028841-06:00 amdgpu 0000:01:00.0: poison is consumed by client 5, kick off gpu reset flow\n"
            "kern  :err   : 2024-11-24T17:53:26,028841-06:00 amdgpu 0000:02:00.0: amdgpu: Poison is created\n"
        )
    )

    analyzer = DmesgAnalyzer(system_info=system_info)
    res = analyzer.analyze_data(
        dmesg_data, args=DmesgAnalyzerArgs(check_unknown_dmesg_errors=False)
    )

    assert res.status == ExecutionStatus.ERROR
    assert len(res.events) == 4

    poison_consumed_events = [e for e in res.events if e.description == "RAS Poison Consumed"]
    poison_created_events = [e for e in res.events if e.description == "RAS Poison created"]

    assert len(poison_consumed_events) == 2
    assert len(poison_created_events) == 2

    for event in res.events:
        assert event.priority == EventPriority.ERROR
        assert event.category == "RAS"


def test_bad_page_threshold(system_info):
    dmesg_data = DmesgData(
        dmesg_content=(
            "kern  :err   : 2024-11-24T17:53:23,028841-06:00 amdgpu 0000:08:00.0: amdgpu: Saved bad pages 176 reaches threshold value 128\n"
            "kern  :info  : 2024-11-24T17:53:24,028841-06:00 Normal log entry\n"
            "kern  :err   : 2024-11-24T17:53:25,028841-06:00 amdgpu: Saved bad pages 200 reaches threshold value 128\n"
        )
    )

    analyzer = DmesgAnalyzer(system_info=system_info)
    res = analyzer.analyze_data(
        dmesg_data, args=DmesgAnalyzerArgs(check_unknown_dmesg_errors=False)
    )

    assert res.status == ExecutionStatus.ERROR
    assert len(res.events) == 2

    for event in res.events:
        assert event.description == "Bad page threshold exceeded"
        assert event.priority == EventPriority.ERROR
        assert event.category == "RAS"
        match_content = event.data["match_content"]
        if isinstance(match_content, list):
            assert "Saved bad pages" in match_content[0]
        else:
            assert "Saved bad pages" in match_content


def test_apei_hardware_error(system_info):
    dmesg_data = DmesgData(
        dmesg_content=(
            "kern  :err   : 2024-09-21T06:12:53,907220-05:00 {1}[Hardware Error]: Hardware error from APEI Generic Hardware Error Source: 1\n"
            "kern  :err   : 2024-09-21T06:12:53,907220-05:00 {1}[Hardware Error]: event severity: recoverable\n"
            "kern  :err   : 2024-09-21T06:12:53,907220-05:00 {1}[Hardware Error]:  Error 0, type: recoverable\n"
            "kern  :err   : 2024-09-21T06:12:53,907220-05:00 {1}[Hardware Error]:   section_type: PCIe error\n"
            "kern  :err   : 2024-09-21T06:12:53,907220-05:00 {1}[Hardware Error]:   port_type: 4, root port\n"
            "kern  :err   : 2024-09-21T06:12:53,907220-05:00 {1}[Hardware Error]:   version: 3.0\n"
            "kern  :err   : 2024-09-21T06:12:53,907220-05:00 {1}[Hardware Error]:   command: 0x0547, status: 0x4010\n"
            "kern  :err   : 2024-09-21T06:12:53,907220-05:00 {1}[Hardware Error]:   device_id: 0000:54:01.0\n"
            "kern  :err   : 2024-09-21T06:12:53,907220-05:00 {1}[Hardware Error]:   slot: 19\n"
            "kern  :err   : 2024-09-21T06:12:53,907220-05:00 {1}[Hardware Error]:   secondary_bus: 0x55\n"
            "kern  :err   : 2024-09-21T06:12:53,907220-05:00 {1}[Hardware Error]:   vendor_id: 0x8086, device_id: 0x352a\n"
            "kern  :err   : 2024-09-21T06:12:53,907220-05:00 {1}[Hardware Error]:   class_code: 060400\n"
            "kern  :err   : 2024-09-21T06:12:53,907220-05:00 {1}[Hardware Error]:   bridge: secondary_status: 0x2000, control: 0x0003\n"
            "kern  :info  : 2024-09-21T06:12:54,000000-05:00 Normal log entry\n"
        )
    )

    analyzer = DmesgAnalyzer(system_info=system_info)
    res = analyzer.analyze_data(
        dmesg_data, args=DmesgAnalyzerArgs(check_unknown_dmesg_errors=False)
    )

    assert res.status == ExecutionStatus.ERROR
    assert len(res.events) == 1

    event = res.events[0]
    assert event.description == "RAS Hardware Error"
    assert event.priority == EventPriority.ERROR
    assert event.category == "RAS"
    match_content = event.data["match_content"]
    if isinstance(match_content, list):
        assert any(
            "Hardware error from APEI Generic Hardware Error Source" in line
            for line in match_content
        )
    else:
        assert "Hardware error from APEI Generic Hardware Error Source" in match_content


def test_error_address_pa(system_info):
    dmesg_data = DmesgData(
        dmesg_content=(
            "kern  :err   : 2024-11-24T17:53:23,028841-06:00 amdgpu 0000:08:00.0: amdgpu: Error Address(PA):0x60d1a4480  Row:0x1834 Col:0x0  Bank:0x7 Channel:0x74\n"
            "kern  :info  : 2024-11-24T17:53:24,028841-06:00 Normal log entry\n"
            "kern  :err   : 2024-11-24T17:53:25,028841-06:00 Error Address(PA):0x12345678  Row:0x100 Col:0x5  Bank:0x2 Channel:0x10\n"
        )
    )

    analyzer = DmesgAnalyzer(system_info=system_info)
    res = analyzer.analyze_data(
        dmesg_data, args=DmesgAnalyzerArgs(check_unknown_dmesg_errors=False)
    )

    assert res.status == ExecutionStatus.ERROR
    assert len(res.events) == 2

    for event in res.events:
        assert event.description == "Error Address"
        assert event.priority == EventPriority.ERROR
        assert event.category == "RAS"
        match_content = event.data["match_content"]
        if isinstance(match_content, list):
            content_str = " ".join(match_content)
        else:
            content_str = match_content
        assert "Error Address(PA)" in content_str
        assert "Row:" in content_str


def test_fixture_file_ras_detection(system_info):
    fixture_path = (
        pathlib.Path(__file__).parent.parent.parent / "functional" / "fixtures" / "dmesg_sample.log"
    )
    with open(fixture_path, "r") as f:
        fixture_content = f.read()

    dmesg_data = DmesgData(dmesg_content=fixture_content)
    analyzer = DmesgAnalyzer(system_info=system_info)
    res = analyzer.analyze_data(
        dmesg_data, args=DmesgAnalyzerArgs(check_unknown_dmesg_errors=False)
    )

    assert res.status == ExecutionStatus.ERROR

    descriptions = [e.description for e in res.events]
    assert len(res.events) >= 6, f"Expected at least 6 errors, found {len(res.events)}"
    assert "RAS Poison Consumed" in descriptions
    assert "RAS Poison created" in descriptions
    assert "Bad page threshold exceeded" in descriptions
    assert "RAS Hardware Error" in descriptions
    assert "Error Address" in descriptions
    assert "ACA Error" in descriptions


def test_combined_ras_errors(system_info):
    dmesg_data = DmesgData(
        dmesg_content=(
            "kern  :err   : 2024-11-24T17:53:23,028841-06:00 amdgpu 0000:68:00.0: {14}poison is consumed by client 12, kick off gpu reset flow\n"
            "kern  :err   : 2024-11-24T17:53:23,028841-06:00 amdgpu 0000:68:00.0: {15}Poison is created\n"
            "kern  :err   : 2024-11-24T17:53:23,028841-06:00 amdgpu 0000:08:00.0: amdgpu: Saved bad pages 176 reaches threshold value 128\n"
            "kern  :err   : 2024-09-21T06:12:53,907220-05:00 {1}[Hardware Error]: Hardware error from APEI Generic Hardware Error Source: 1\n"
            "kern  :err   : 2024-09-21T06:12:53,907220-05:00 {1}[Hardware Error]: event severity: recoverable\n"
            "kern  :err   : 2024-09-21T06:12:53,907220-05:00 {1}[Hardware Error]:  Error 0, type: recoverable\n"
            "kern  :err   : 2024-11-24T17:53:23,028841-06:00 amdgpu 0000:08:00.0: amdgpu: Error Address(PA):0x60d1a4480  Row:0x1834 Col:0x0  Bank:0x7 Channel:0x74\n"
        )
    )

    analyzer = DmesgAnalyzer(system_info=system_info)
    res = analyzer.analyze_data(
        dmesg_data, args=DmesgAnalyzerArgs(check_unknown_dmesg_errors=False)
    )

    assert res.status == ExecutionStatus.ERROR
    assert len(res.events) == 5

    descriptions = [e.description for e in res.events]
    assert "RAS Poison Consumed" in descriptions
    assert "RAS Poison created" in descriptions
    assert "Bad page threshold exceeded" in descriptions
    assert "RAS Hardware Error" in descriptions
    assert "Error Address" in descriptions

    for event in res.events:
        assert event.category == "RAS"
        assert event.priority == EventPriority.ERROR
