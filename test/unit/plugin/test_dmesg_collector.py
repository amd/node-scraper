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

import pytest

from nodescraper.connection.inband.inband import CommandArtifact
from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.interfaces.task import SystemCompatibilityError
from nodescraper.models.systeminfo import OSFamily
from nodescraper.plugins.inband.dmesg.dmesg_collector import DmesgCollector
from nodescraper.plugins.inband.dmesg.dmesgdata import DmesgData


def test_get_new_lines():
    """Test the new lines method"""

    initial_dmesg = (
        "2023-06-01T01:00:00,685236-05:00 test message1\n"
        "2023-06-01T02:30:00,685106-05:00 test message2\n"
        "2023-06-01T03:00:00,983214-05:00 test message3\n"
        "2023-06-01T03:20:00,635178-05:00 test message4\n"
        "2023-06-01T03:25:00,635178-05:00 test message5"
    )

    new_dmesg = (
        "2023-06-01T01:00:00,685236-05:00 test message1\n"
        "2023-06-01T02:30:00,685106-05:00 test message2\n"
        "2023-06-01T03:00:00,983214-05:00 test message3\n"
        "2023-06-01T03:20:00,635178-05:00 test message4\n"
        "2023-06-01T03:25:00,635178-05:00 test message5\n"
        "2023-06-01T03:30:00,635178-05:00 test message7\n"
        "2023-06-01T03:35:00,635178-05:00 test message8\n"
        "2023-06-01T03:36:00,635178-05:00 test message9"
    )

    exp_new_lines = (
        "2023-06-01T03:30:00,635178-05:00 test message7\n"
        "2023-06-01T03:35:00,635178-05:00 test message8\n"
        "2023-06-01T03:36:00,635178-05:00 test message9"
    )

    new_lines = DmesgData.get_new_dmesg_lines(initial_dmesg, new_dmesg)

    assert new_lines == exp_new_lines


def test_dmesg_collection(system_info, conn_mock):
    system_info.os_family = OSFamily.LINUX
    collector = DmesgCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.INTERACTIVE,
        connection=conn_mock,
    )

    dmesg = (
        "2023-06-01T01:00:00,685236-05:00 test message1\n"
        "2023-06-01T02:30:00,685106-05:00 test message2\n"
        "2023-06-01T03:00:00,983214-05:00 test message3\n"
        "      kernel:[Hardware Error]: IPID: 0x0001400136430400, Syndrome: 0x0000000000001005\n"
        "      Message from syslogd@pp-128-b6-2 at Feb  8 08:25:18 ...\n"
        "   \n"
        "2023-06-01T03:20:00,635178-05:00 test message4\n"
        "2023-06-01T03:25:00,635178-05:00 test message5\n"
    )
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=0,
        stdout=dmesg,
        stderr="",
        command="dmesg --time-format iso",
    )

    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.OK
    assert data is not None
    assert data.dmesg_content == dmesg


def test_bad_exit_code(conn_mock, system_info):

    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=1,
        stdout="2023-06-01T01:00:00,685236-05:00 test message1\n",
        stderr="",
        command="dmesg --time-format iso",
    )

    collector = DmesgCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.INTERACTIVE,
        connection=conn_mock,
    )

    res, _ = collector.collect_data()
    assert res.status == ExecutionStatus.ERROR
    assert len(res.events) == 1
    assert res.events[0].description == "Error reading dmesg"


def test_run_dmesg_windows(conn_mock, system_info):
    system_info.os_family = OSFamily.WINDOWS
    with pytest.raises(SystemCompatibilityError, match="WINDOWS OS family is not supported"):
        DmesgCollector(
            system_info=system_info,
            system_interaction_level=SystemInteractionLevel.INTERACTIVE,
            connection=conn_mock,
        )


def test_data_model():
    dmesg_data1 = DmesgData.import_model(
        {"dmesg_content": "2023-06-01T01:00:00,685236-05:00 test message1\n"}
    )
    dmesg_data2 = DmesgData.import_model(
        {"dmesg_content": "2023-06-01T02:30:00,685106-05:00 test message2\n"}
    )

    dmesg_data2.merge_data(dmesg_data1)
    assert dmesg_data2.dmesg_content == (
        "2023-06-01T01:00:00,685236-05:00 test message1\n2023-06-01T02:30:00,685106-05:00 test message2"
    )


class DummyRes:
    def __init__(self, command="", stdout="", exit_code=0, stderr=""):
        self.command = command
        self.stdout = stdout
        self.exit_code = exit_code
        self.stderr = stderr


def get_collector(monkeypatch, run_map, system_info, conn_mock):
    c = DmesgCollector(
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


def test_collect_rotations_good_path(monkeypatch, system_info, conn_mock):
    ls_out = (
        "\n".join(
            [
                "/var/log/dmesg_log",
                "/var/log/dmesg.1",
                "/var/log/dmesg.2.gz",
                "/var/log/dmesg.10.gz",
            ]
        )
        + "\n"
    )

    def run_map(cmd, **kwargs):
        if cmd.startswith("ls -1 /var/log/dmesg"):
            return DummyRes(command=cmd, stdout=ls_out, exit_code=0)
        if cmd.startswith("cat '"):
            if "/var/log/dmesg.1'" in cmd:
                return DummyRes(command=cmd, stdout="dmesg.1 content\n", exit_code=0)
            if "/var/log/dmesg_log'" in cmd:
                return DummyRes(command=cmd, stdout="dmesg content\n", exit_code=0)
        if "gzip -dc" in cmd and "/var/log/dmesg.2.gz" in cmd:
            return DummyRes(command=cmd, stdout="gz2 content\n", exit_code=0)
        if "gzip -dc" in cmd and "/var/log/dmesg.10.gz" in cmd:
            return DummyRes(command=cmd, stdout="gz10 content\n", exit_code=0)
        return DummyRes(command=cmd, stdout="", exit_code=1, stderr="unexpected")

    c = get_collector(monkeypatch, run_map, system_info, conn_mock)

    c._collect_dmesg_rotations()

    names = {a.filename for a in c.result.artifacts}
    assert names == {"dmesg_log.log", "dmesg.1.log", "dmesg.2.gz.log", "dmesg.10.gz.log"}

    descs = [e["description"] for e in c._events]
    assert "Collected dmesg rotated files" in descs


def test_collect_rotations_no_files(monkeypatch, system_info, conn_mock):
    def run_map(cmd, **kwargs):
        if cmd.startswith("ls -1 /var/log/dmesg"):
            return DummyRes(command=cmd, stdout="", exit_code=0)
        return DummyRes(command=cmd, stdout="", exit_code=1)

    c = get_collector(monkeypatch, run_map, system_info, conn_mock)

    c._collect_dmesg_rotations()

    assert c.result.artifacts == []

    events = c._events
    assert any(
        e["description"].startswith("No /var/log/dmesg files found")
        and e["priority"].name == "WARNING"
        for e in events
    )


def test_collect_rotations_gz_failure(monkeypatch, system_info, conn_mock):
    ls_out = "/var/log/dmesg.2.gz\n"

    def run_map(cmd, **kwargs):
        if cmd.startswith("ls -1 /var/log/dmesg"):
            return DummyRes(command=cmd, stdout=ls_out, exit_code=0)
        if "gzip -dc" in cmd and "/var/log/dmesg.2.gz" in cmd:
            return DummyRes(command=cmd, stdout="", exit_code=1, stderr="gzip: not found")
        return DummyRes(command=cmd, stdout="", exit_code=1)

    c = get_collector(monkeypatch, run_map, system_info, conn_mock)

    c._collect_dmesg_rotations()

    assert c.result.artifacts == []

    fail_events = [
        e for e in c._events if e["description"] == "Some dmesg files could not be collected."
    ]
    assert fail_events, "Expected a failure event"
    failed = fail_events[-1]["data"]["failed"]
    assert any(item["path"].endswith("/var/log/dmesg.2.gz") for item in failed)


def test_collect_data_integration(monkeypatch, system_info, conn_mock):
    def run_map(cmd, **kwargs):
        if cmd == DmesgCollector.DMESG_CMD:
            return DummyRes(command=cmd, stdout="DMESG OUTPUT\n", exit_code=0)
        if cmd.startswith("ls -1 /var/log/dmesg"):
            return DummyRes(command=cmd, stdout="/var/log/dmesg\n", exit_code=0)
        if cmd.startswith("cat '") and "/var/log/dmesg'" in cmd:
            return DummyRes(command=cmd, stdout="dmesg file content\n", exit_code=0)
        return DummyRes(command=cmd, stdout="", exit_code=1)

    c = get_collector(monkeypatch, run_map, system_info, conn_mock)

    result, data = c.collect_data()

    assert isinstance(data, DmesgData)
    assert data.dmesg_content == "DMESG OUTPUT\n"
