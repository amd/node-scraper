###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
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
from pathlib import Path
from typing import Optional

import pytest
from pydantic import BaseModel, Field

from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.enums.systemlocation import SystemLocation
from nodescraper.interfaces.task import SystemCompatibilityError
from nodescraper.models.systeminfo import OSFamily, SystemInfo
from nodescraper.plugins.inband.mca_register_decode import (
    mca_register_decode_collector as collector_mod,
)
from nodescraper.plugins.inband.mca_register_decode import (
    register_tool as register_tool_mod,
)
from nodescraper.plugins.inband.mca_register_decode.collector_args import (
    McaRegisterDecodeCollectorArgs,
)
from nodescraper.plugins.inband.mca_register_decode.mca_register_decode_analyzer import (
    McaRegisterDecodeAnalyzer,
)
from nodescraper.plugins.inband.mca_register_decode.mca_register_decode_collector import (
    McaRegisterDecodeCollector,
)
from nodescraper.plugins.inband.mca_register_decode.mca_register_decode_data import (
    McaRegisterDecodeDataModel,
)
from nodescraper.plugins.inband.mca_register_decode.mca_register_decode_plugin import (
    McaRegisterDecodePlugin,
)
from nodescraper.plugins.inband.mca_register_decode.mca_register_session import (
    McaRegisterDecodeSession,
)


class FakeRecord(BaseModel):
    cpu: int
    bank: int


class FakeCollection(BaseModel):
    stats: Optional[dict] = None
    records: list[FakeRecord] = Field(default_factory=list)


class FakeDecodedResult(BaseModel):
    stats: Optional[dict] = None
    records: list[dict] = Field(default_factory=list)


class FakeInterval:
    def __init__(self, cpu, seconds):
        self.cpu = cpu
        self.seconds = seconds


class FakeRegisterTool:
    def __init__(self):
        self.calls = []
        self.intervals = [FakeInterval(0, 5)]

    def health_check(self):
        self.calls.append("health_check")
        return 0

    def get_check_intervals(self, threads=None):
        self.calls.append(("get_check_intervals", threads))
        return list(self.intervals)

    def set_check_interval(self, seconds, threads=None):
        self.calls.append(("set_check_interval", seconds, threads))
        return len(threads) if threads else len(self.intervals)

    def collect(self, threads=None, banks=None, verbose=False, capture_all=False) -> FakeCollection:
        self.calls.append("collect")
        assert threads == [0]
        assert banks == [1]
        assert verbose is False
        assert capture_all is True
        return FakeCollection(stats={"cpus_found": 1}, records=[FakeRecord(cpu=0, bank=1)])

    def record_from_row(self, row):
        return FakeRecord(cpu=int(row["cpu"]), bank=int(row["bank"]))

    def decode_records(self, records):
        self.calls.append("decode_records")
        rows = records.records if hasattr(records, "records") else records
        return FakeDecodedResult(
            stats=None,
            records=[
                {"cpu": row.cpu, "bank": row.bank, "decoded": {"summary": "example"}}
                for row in rows
            ],
        )

    def decode_dmesg(self, text, gpu=None):
        self.calls.append(("decode_dmesg", text, gpu))
        if not text:
            return FakeDecodedResult(records=[])
        return FakeDecodedResult(records=[{"cpu": 0, "bank": 1, "decoded": {"summary": "dmesg"}}])

    def clear(self, threads=None, wait_seconds=2.0):
        self.calls.append(("clear", threads, wait_seconds))
        return 1


class FakeEntryPoint:
    def __init__(self, name="tool-a", value="example.provider:ExampleTool"):
        self.name = name
        self.value = value

    def load(self):
        return FakeRegisterTool


class FakeEntryPoints:
    def __init__(self, entries, expected_group="mca_tool"):
        self._entries = entries
        self._expected_group = expected_group

    def select(self, group):
        assert group == self._expected_group
        return list(self._entries)


@pytest.fixture
def collector(system_info, conn_mock):
    system_info.sku = "MI450"
    return McaRegisterDecodeCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


def test_plugin_wires_collector_analyzer_and_model():
    assert McaRegisterDecodePlugin.DATA_MODEL is McaRegisterDecodeDataModel
    assert McaRegisterDecodePlugin.COLLECTOR is McaRegisterDecodeCollector
    assert McaRegisterDecodePlugin.ANALYZER is McaRegisterDecodeAnalyzer
    assert McaRegisterDecodePlugin.ANALYZER_ARGS is None
    assert McaRegisterDecodeCollector.SUPPORTED_SKUS == {"MI450", "MI455", "MI4XX"}
    assert McaRegisterDecodeCollectorArgs().tool_group is None


def test_collector_rejects_unsupported_sku(conn_mock):
    system_info = SystemInfo(
        name="test_host",
        platform="X",
        os_family=OSFamily.LINUX,
        sku="MI300",
    )
    with pytest.raises(SystemCompatibilityError, match="MI300 SKU is not supported"):
        McaRegisterDecodeCollector(
            system_info=system_info,
            system_interaction_level=SystemInteractionLevel.PASSIVE,
            connection=conn_mock,
        )


def test_discover_register_tool_requires_group():
    with pytest.raises(RuntimeError, match="tool_group is required"):
        register_tool_mod.discover_register_tool()


def test_discover_register_tool_from_entry_point(monkeypatch):
    monkeypatch.setattr(
        register_tool_mod,
        "entry_points",
        lambda: FakeEntryPoints([FakeEntryPoint()]),
    )
    assert isinstance(
        register_tool_mod.discover_register_tool(group="mca_tool"),
        FakeRegisterTool,
    )


def test_discover_register_tool_uses_custom_group(monkeypatch):
    monkeypatch.setattr(
        register_tool_mod,
        "entry_points",
        lambda: FakeEntryPoints([FakeEntryPoint()], expected_group="custom_tool"),
    )
    assert isinstance(
        register_tool_mod.discover_register_tool(group="custom_tool"),
        FakeRegisterTool,
    )


def test_discover_register_tool_requires_name_when_multiple(monkeypatch):
    monkeypatch.setattr(
        register_tool_mod,
        "entry_points",
        lambda: FakeEntryPoints(
            [
                FakeEntryPoint(name="tool-a", value="example.provider:A"),
                FakeEntryPoint(name="tool-b", value="example.provider:B"),
            ]
        ),
    )
    with pytest.raises(RuntimeError, match="Multiple mca_tool entry points"):
        register_tool_mod.discover_register_tool(group="mca_tool")
    assert isinstance(
        register_tool_mod.discover_register_tool(name="tool-b", group="mca_tool"),
        FakeRegisterTool,
    )


def _stage_collected_dmesg(collector, tmp_path: Path, text: str) -> None:
    run = tmp_path / "run"
    dmesg_dir = run / "dmesg_plugin" / "dmesg_collector"
    dmesg_dir.mkdir(parents=True)
    (dmesg_dir / "dmesg.log").write_text(text, encoding="utf-8")
    collector.log_path = str(run / "mca_register_decode_plugin" / "mca_register_decode_collector")


def _forbid_command(*args, **kwargs):
    raise AssertionError("dmesg command should not run")


def test_collect_uses_register_tool(collector, monkeypatch, tmp_path):
    tool = FakeRegisterTool()

    def _discover(name=None, group=None):
        assert group == "mca_tool"
        assert name is None
        return tool

    _stage_collected_dmesg(collector, tmp_path, "kernel log line")
    monkeypatch.setattr(collector_mod, "discover_register_tool", _discover)
    monkeypatch.setattr(collector, "_run_sut_cmd", _forbid_command)
    result, data = collector.collect_data(
        McaRegisterDecodeCollectorArgs(
            tool_group="mca_tool",
            threads=[0],
            banks=[1],
            capture_all=True,
            gpu="example-gpu",
        )
    )
    assert result.status == ExecutionStatus.OK
    assert result.message == (
        "Collected 1 MCA register record(s) and decoded 1 MSR record(s) and 1 dmesg record(s)"
    )
    assert data.records == [{"cpu": 0, "bank": 1}]
    assert data.stats == {"cpus_found": 1}
    assert data.decoded_records == [{"cpu": 0, "bank": 1, "decoded": {"summary": "example"}}]
    assert data.dmesg_decoded_records == [{"cpu": 0, "bank": 1, "decoded": {"summary": "dmesg"}}]
    assert ("set_check_interval", 0, [0]) in tool.calls
    assert ("decode_dmesg", "kernel log line", "example-gpu") in tool.calls
    assert ("clear", [0], 2.0) in tool.calls
    assert ("set_check_interval", 5, [0]) in tool.calls
    assert tool.calls.index(("set_check_interval", 0, [0])) < tool.calls.index("collect")
    assert tool.calls.index("decode_records") < tool.calls.index(
        ("decode_dmesg", "kernel log line", "example-gpu")
    )
    assert tool.calls.index(("clear", [0], 2.0)) < tool.calls.index(("set_check_interval", 5, [0]))


def test_collect_skips_when_remote(collector, monkeypatch):
    collector.system_info.location = SystemLocation.REMOTE

    def _discover(name=None, group=None):
        raise AssertionError("register tool should not be loaded for a remote system")

    monkeypatch.setattr(collector_mod, "discover_register_tool", _discover)
    result, data = collector.collect_data(McaRegisterDecodeCollectorArgs(tool_group="mca_tool"))
    assert result.status == ExecutionStatus.NOT_RAN
    assert data is None
    assert result.message == "MCA register decode is only supported on local"
    assert result.events[0].description == result.message


def test_analyze_skips_when_remote(system_info):
    system_info.location = SystemLocation.REMOTE
    analyzer = McaRegisterDecodeAnalyzer(system_info=system_info)
    data = McaRegisterDecodeDataModel(stats={"cpus_found": 1}, records=[{"cpu": 0, "bank": 1}])
    result = analyzer.analyze_data(data)
    assert result.status == ExecutionStatus.NOT_RAN
    assert result.message == "MCA register decode is only supported on local"
    assert result.events[0].description == result.message


def test_collect_reports_missing_tool_group(collector, monkeypatch):
    monkeypatch.setattr(
        collector_mod, "discover_register_tool", register_tool_mod.discover_register_tool
    )
    result, data = collector.collect_data()
    assert result.status == ExecutionStatus.ERROR
    assert data is None
    assert "tool_group is required" in result.message


def test_collect_reports_health_check_failure(collector, monkeypatch):
    tool = FakeRegisterTool()
    tool.health_check = lambda: 8
    monkeypatch.setattr(collector_mod, "discover_register_tool", lambda name=None, group=None: tool)
    result, data = collector.collect_data(McaRegisterDecodeCollectorArgs(tool_group="mca_tool"))
    assert result.status == ExecutionStatus.ERROR
    assert data is None
    assert "MCA register tool health check failed" in result.message


def test_collect_reports_missing_entry_point(collector, monkeypatch):
    def _missing(name=None, group=None):
        raise RuntimeError(f"No {group} entry point is installed")

    monkeypatch.setattr(collector_mod, "discover_register_tool", _missing)
    result, data = collector.collect_data(McaRegisterDecodeCollectorArgs(tool_group="mca_tool"))
    assert result.status == ExecutionStatus.ERROR
    assert data is None
    assert "mca_tool" in result.message


def test_analyze_requires_records_decoded_during_collection(system_info):
    analyzer = McaRegisterDecodeAnalyzer(system_info=system_info)
    data = McaRegisterDecodeDataModel(stats={"cpus_found": 1}, records=[{"cpu": 0, "bank": 1}])
    result = analyzer.analyze_data(data)
    assert result.status == ExecutionStatus.ERROR
    assert "MCA register records were not decoded during collection" in result.message


def test_analyze_reports_records_already_decoded(system_info):
    analyzer = McaRegisterDecodeAnalyzer(system_info=system_info)
    data = McaRegisterDecodeDataModel(
        records=[{"cpu": 0, "bank": 1}],
        decoded_records=[{"cpu": 0, "bank": 1}],
        dmesg_decoded_records=[{"cpu": 1, "bank": 2}],
    )
    result = analyzer.analyze_data(data)
    assert result.status == ExecutionStatus.OK
    assert result.message == "Decoded 1 MCA register record(s) and 1 dmesg record(s)"


def test_collect_restores_check_interval_when_collect_fails(collector, monkeypatch):
    tool = FakeRegisterTool()

    def _boom(threads=None, banks=None, verbose=False, capture_all=False):
        tool.calls.append("collect")
        raise RuntimeError("scan failed")

    tool.collect = _boom
    monkeypatch.setattr(collector_mod, "discover_register_tool", lambda name=None, group=None: tool)
    result, data = collector.collect_data(
        McaRegisterDecodeCollectorArgs(
            tool_group="mca_tool",
            threads=[0],
            banks=[1],
            capture_all=True,
        )
    )
    assert result.status == ExecutionStatus.ERROR
    assert data is None
    assert "scan failed" in result.message
    assert ("set_check_interval", 0, [0]) in tool.calls
    assert ("set_check_interval", 5, [0]) in tool.calls


def test_collect_skips_interval_changes_when_caller_manages_them(collector, monkeypatch, tmp_path):
    tool = FakeRegisterTool()
    _stage_collected_dmesg(collector, tmp_path, "kernel log line")
    monkeypatch.setattr(collector_mod, "discover_register_tool", lambda name=None, group=None: tool)
    monkeypatch.setattr(collector, "_run_sut_cmd", _forbid_command)
    result, data = collector.collect_data(
        McaRegisterDecodeCollectorArgs(
            tool_group="mca_tool",
            threads=[0],
            banks=[1],
            capture_all=True,
            manage_check_interval=False,
        )
    )
    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert not any(
        isinstance(call, tuple) and call[0] in {"get_check_intervals", "set_check_interval"}
        for call in tool.calls
    )
    assert ("clear", [0], 2.0) in tool.calls


def test_collect_warns_when_collected_dmesg_is_missing(collector, monkeypatch):
    tool = FakeRegisterTool()
    monkeypatch.setattr(collector_mod, "discover_register_tool", lambda name=None, group=None: tool)
    monkeypatch.setattr(collector, "_run_sut_cmd", _forbid_command)
    result, data = collector.collect_data(
        McaRegisterDecodeCollectorArgs(
            tool_group="mca_tool",
            threads=[0],
            banks=[1],
            capture_all=True,
        )
    )
    assert result.status == ExecutionStatus.WARNING
    assert data.decoded_records
    assert data.dmesg_decoded_records == []
    assert not any(isinstance(call, tuple) and call[0] == "decode_dmesg" for call in tool.calls)


def test_session_restores_each_saved_interval():
    tool = FakeRegisterTool()
    tool.intervals = [FakeInterval(0, 5), FakeInterval(1, 5), FakeInterval(2, 30)]
    session = McaRegisterDecodeSession(tool)
    assert session.prepare() == 0
    session.suspend_polling()
    assert session.restore() == 3
    assert ("set_check_interval", 0, None) in tool.calls
    assert ("set_check_interval", 5, [0, 1]) in tool.calls
    assert ("set_check_interval", 30, [2]) in tool.calls
