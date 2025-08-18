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

from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.plugins.inband.syslog.syslog_collector import SyslogCollector
from nodescraper.plugins.inband.syslog.syslogdata import SyslogData


class DummyRes:
    def __init__(self, command="", stdout="", exit_code=0, stderr=""):
        self.command = command
        self.stdout = stdout
        self.exit_code = exit_code
        self.stderr = stderr


def get_collector(monkeypatch, run_map, system_info, conn_mock):
    c = SyslogCollector(
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
                "/var/log/syslog",
                "/var/log/syslog.1",
                "/var/log/syslog.2.gz",
                "/var/log/syslog.10.gz",
            ]
        )
        + "\n"
    )

    def run_map(cmd, **kwargs):
        if cmd.startswith("ls -1 /var/log/syslog"):
            return DummyRes(command=cmd, stdout=ls_out, exit_code=0)

        if cmd.startswith("cat "):
            if "/var/log/syslog.1" in cmd:
                return DummyRes(command=cmd, stdout="syslog.1 content\n", exit_code=0)
            if "/var/log/syslog" in cmd:
                return DummyRes(command=cmd, stdout="syslog content\n", exit_code=0)

        if "gzip -dc" in cmd and "/var/log/syslog.2.gz" in cmd:
            return DummyRes(command=cmd, stdout="gz2 content\n", exit_code=0)
        if "gzip -dc" in cmd and "/var/log/syslog.10.gz" in cmd:
            return DummyRes(command=cmd, stdout="gz10 content\n", exit_code=0)

        return DummyRes(command=cmd, stdout="", exit_code=1, stderr="unexpected")

    c = get_collector(monkeypatch, run_map, system_info, conn_mock)

    n = c._collect_syslog_rotations()
    assert n == 4

    names = {a.filename for a in c.result.artifacts}
    assert names == {
        "rotated_syslog.log",
        "rotated_syslog.1.log",
        "rotated_syslog.2.gz.log",
        "rotated_syslog.10.gz.log",
    }

    descs = [e["description"] for e in c._events]
    assert "Collected syslog rotated files" in descs


def test_collect_rotations_no_files(monkeypatch, system_info, conn_mock):
    def run_map(cmd, **kwargs):
        if cmd.startswith("ls -1 /var/log/syslog"):
            return DummyRes(command=cmd, stdout="", exit_code=0)
        return DummyRes(command=cmd, stdout="", exit_code=1)

    c = get_collector(monkeypatch, run_map, system_info, conn_mock)

    n = c._collect_syslog_rotations()
    assert n == 0
    assert c.result.artifacts == []

    assert any(
        e["description"].startswith("No /var/log/syslog files found")
        and getattr(e["priority"], "name", str(e["priority"])) == "WARNING"
        for e in c._events
    )


def test_collect_rotations_gz_failure(monkeypatch, system_info, conn_mock):
    ls_out = "/var/log/syslog.2.gz\n"

    def run_map(cmd, **kwargs):
        if cmd.startswith("ls -1 /var/log/syslog"):
            return DummyRes(command=cmd, stdout=ls_out, exit_code=0)
        if "gzip -dc" in cmd and "/var/log/syslog.2.gz" in cmd:
            return DummyRes(command=cmd, stdout="", exit_code=1, stderr="gzip: not found")
        return DummyRes(command=cmd, stdout="", exit_code=1)

    c = get_collector(monkeypatch, run_map, system_info, conn_mock)

    n = c._collect_syslog_rotations()
    assert n == 0
    assert c.result.artifacts == []

    fail_events = [
        e for e in c._events if e["description"] == "Some syslog files could not be collected."
    ]
    assert fail_events, "Expected a failure event"
    failed = fail_events[-1]["data"]["failed"]
    assert any(item["path"].endswith("/var/log/syslog.2.gz") for item in failed)


def test_collect_data_integration(monkeypatch, system_info, conn_mock):
    ls_out = "/var/log/syslog\n"

    def run_map(cmd, **kwargs):
        if cmd.startswith("ls -1 /var/log/syslog"):
            return DummyRes(command=cmd, stdout=ls_out, exit_code=0)
        if cmd.startswith("cat ") and "/var/log/syslog" in cmd:
            return DummyRes(command=cmd, stdout="syslog file content\n", exit_code=0)
        return DummyRes(command=cmd, stdout="", exit_code=1)

    c = get_collector(monkeypatch, run_map, system_info, conn_mock)

    result, data = c.collect_data()
    assert isinstance(data, SyslogData)
    assert data.syslog_logs == 1
    assert c.result.message == "Syslog data collected"
