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
from nodescraper.plugins.inband.journal.journal_collector import JournalCollector
from nodescraper.plugins.inband.journal.journaldata import JournalData


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


def test_get_journals_happy_path(monkeypatch, system_info, conn_mock):
    paths = [
        "/var/log/journal/m1/system.journal",
        "/var/log/journal/m1/system@0000000000000001-0000000000000002.journal",
        "/var/log/journal/m2/system.journal",
    ]
    ls_out = "\n".join(paths) + "\n"

    def run_map(cmd, **kwargs):
        if cmd.startswith("ls -1 /var/log/journal"):
            return DummyRes(command=cmd, stdout=ls_out, exit_code=0)

        if cmd.startswith("journalctl ") and "--file=" in cmd:
            if paths[0] in cmd:
                return DummyRes(cmd, stdout='{"MESSAGE":"a"}\n', exit_code=0)
            if paths[1] in cmd:
                return DummyRes(cmd, stdout=b'{"MESSAGE":"b"}\n', exit_code=0)
            if paths[2] in cmd:
                return DummyRes(cmd, stdout='{"MESSAGE":"c"}\n', exit_code=0)

        return DummyRes(command=cmd, stdout="", exit_code=1, stderr="unexpected")

    c = get_collector(monkeypatch, run_map, system_info, conn_mock)

    collected = c._get_journals()
    assert len(collected) == 3

    expected_names = {
        "journalctl__var__log__journal__m1__system.journal.json",
        "journalctl__var__log__journal__m1__system@0000000000000001-0000000000000002.journal.json",
        "journalctl__var__log__journal__m2__system.journal.json",
    }
    names = {a.filename for a in c.result.artifacts}
    assert names == expected_names

    contents = {a.filename: a.contents for a in c.result.artifacts}
    assert (
        contents["journalctl__var__log__journal__m1__system.journal.json"].strip()
        == '{"MESSAGE":"a"}'
    )
    assert (
        contents[
            "journalctl__var__log__journal__m1__system@0000000000000001-0000000000000002.journal.json"
        ].strip()
        == '{"MESSAGE":"b"}'
    )
    assert (
        contents["journalctl__var__log__journal__m2__system.journal.json"].strip()
        == '{"MESSAGE":"c"}'
    )

    assert any(
        evt.get("description") == "Collected journal logs."
        and getattr(evt.get("priority"), "name", str(evt.get("priority"))) == "INFO"
        for evt in c._events
    )
    assert c.result.message == "journalctl logs collected"


def test_get_journals_no_files(monkeypatch, system_info, conn_mock):
    def run_map(cmd, **kwargs):
        if cmd.startswith("ls -1 /var/log/journal"):
            return DummyRes(command=cmd, stdout="", exit_code=0)
        return DummyRes(command=cmd, stdout="", exit_code=1)

    c = get_collector(monkeypatch, run_map, system_info, conn_mock)

    collected = c._get_journals()
    assert collected == []
    assert c.result.artifacts == []

    assert any(
        evt.get("description", "").startswith("No /var/log/journal files found")
        and getattr(evt.get("priority"), "name", str(evt.get("priority"))) == "WARNING"
        for evt in c._events
    )


def test_get_journals_partial_failure(monkeypatch, system_info, conn_mock):
    ok_path = "/var/log/journal/m1/system.journal"
    bad_path = "/var/log/journal/m1/system@bad.journal"
    ls_out = ok_path + "\n" + bad_path + "\n"

    def run_map(cmd, **kwargs):
        if cmd.startswith("ls -1 /var/log/journal"):
            return DummyRes(command=cmd, stdout=ls_out, exit_code=0)

        if cmd.startswith("journalctl ") and "--file=" in cmd:
            if ok_path in cmd:
                return DummyRes(cmd, stdout='{"MESSAGE":"ok"}\n', exit_code=0)
            if bad_path in cmd:
                return DummyRes(cmd, stdout="", exit_code=1, stderr="cannot read")

        return DummyRes(command=cmd, stdout="", exit_code=1)

    c = get_collector(monkeypatch, run_map, system_info, conn_mock)

    collected = c._get_journals()
    assert collected == ["journalctl__var__log__journal__m1__system.journal.json"]
    assert [a.filename for a in c.result.artifacts] == [
        "journalctl__var__log__journal__m1__system.journal.json"
    ]

    assert any(
        evt.get("description") == "Some journal files could not be read with journalctl."
        and getattr(evt.get("priority"), "name", str(evt.get("priority"))) == "WARNING"
        for evt in c._events
    )


def test_collect_data_integration(monkeypatch, system_info, conn_mock):
    dummy_path = "/var/log/journal/m1/system.journal"
    ls_out = dummy_path + "\n"

    def run_map(cmd, **kwargs):
        if cmd.startswith("ls -1 /var/log/journal"):
            return DummyRes(command=cmd, stdout=ls_out, exit_code=0)
        if cmd.startswith("journalctl ") and "--file=" in cmd and dummy_path in cmd:
            return DummyRes(command=cmd, stdout='{"MESSAGE":"hello"}\n', exit_code=0)
        return DummyRes(command=cmd, stdout="", exit_code=1)

    c = get_collector(monkeypatch, run_map, system_info, conn_mock)

    result, data = c.collect_data()
    assert isinstance(data, JournalData)

    expected_name = "journalctl__var__log__journal__m1__system.journal.json"
    assert data.journal_logs == [expected_name]
    assert c.result.message == "journalctl logs collected"

    assert [a.filename for a in c.result.artifacts] == [expected_name]
