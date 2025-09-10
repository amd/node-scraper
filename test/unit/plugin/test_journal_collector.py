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


def test_collect_data_integration(monkeypatch, system_info, conn_mock):
    def run_map(cmd, **kwargs):
        return DummyRes(command=cmd, stdout='{"MESSAGE":"hello"}\n', exit_code=0)

    c = get_collector(monkeypatch, run_map, system_info, conn_mock)

    result, data = c.collect_data()
    assert isinstance(data, JournalData)

    assert data.journal_log == '{"MESSAGE":"hello"}\n'
