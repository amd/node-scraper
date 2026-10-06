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
from typing import Optional

import pytest
from pydantic import BaseModel, Field

from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.enums.systemlocation import SystemLocation
from nodescraper.interfaces.task import SystemCompatibilityError
from nodescraper.models.systeminfo import OSFamily, SystemInfo
from nodescraper.plugins.inband.register_decode import (
    register_decode_analyzer as analyzer_mod,
)
from nodescraper.plugins.inband.register_decode import (
    register_decode_collector as collector_mod,
)
from nodescraper.plugins.inband.register_decode import (
    register_tool as register_tool_mod,
)
from nodescraper.plugins.inband.register_decode.analyzer_args import (
    RegisterDecodeAnalyzerArgs,
)
from nodescraper.plugins.inband.register_decode.collector_args import (
    RegisterDecodeCollectorArgs,
)
from nodescraper.plugins.inband.register_decode.register_decode_analyzer import (
    RegisterDecodeAnalyzer,
)
from nodescraper.plugins.inband.register_decode.register_decode_collector import (
    RegisterDecodeCollector,
)
from nodescraper.plugins.inband.register_decode.register_decode_data import (
    RegisterDecodeDataModel,
)
from nodescraper.plugins.inband.register_decode.register_decode_plugin import (
    RegisterDecodePlugin,
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


class FakeRegisterTool:
    def health_check(self):
        return 0

    def collect(self, threads=None, banks=None, verbose=False, capture_all=False) -> FakeCollection:
        assert threads == [0]
        assert banks == [1]
        assert verbose is False
        assert capture_all is True
        return FakeCollection(stats={"cpus_found": 1}, records=[FakeRecord(cpu=0, bank=1)])

    def record_from_row(self, row):
        return FakeRecord(cpu=int(row["cpu"]), bank=int(row["bank"]))

    def decode_records(self, records):
        return FakeDecodedResult(
            stats=None,
            records=[
                {"cpu": row.cpu, "bank": row.bank, "decoded": {"summary": "example"}}
                for row in records
            ],
        )


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
    return RegisterDecodeCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


def test_plugin_wires_collector_analyzer_and_model():
    assert RegisterDecodePlugin.DATA_MODEL is RegisterDecodeDataModel
    assert RegisterDecodePlugin.COLLECTOR is RegisterDecodeCollector
    assert RegisterDecodePlugin.ANALYZER is RegisterDecodeAnalyzer
    assert RegisterDecodePlugin.ANALYZER_ARGS is RegisterDecodeAnalyzerArgs
    assert RegisterDecodeCollector.SUPPORTED_SKUS == {"MI450", "MI455", "MI4XX"}
    assert RegisterDecodeCollectorArgs().tool_group is None
    assert RegisterDecodeAnalyzerArgs().tool_group is None


def test_collector_rejects_unsupported_sku(conn_mock):
    system_info = SystemInfo(
        name="test_host",
        platform="X",
        os_family=OSFamily.LINUX,
        sku="MI300",
    )
    with pytest.raises(SystemCompatibilityError, match="MI300 SKU is not supported"):
        RegisterDecodeCollector(
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


def test_collect_uses_register_tool(collector, monkeypatch):
    def _discover(name=None, group=None):
        assert group == "mca_tool"
        assert name is None
        return FakeRegisterTool()

    monkeypatch.setattr(collector_mod, "discover_register_tool", _discover)
    result, data = collector.collect_data(
        RegisterDecodeCollectorArgs(
            tool_group="mca_tool",
            threads=[0],
            banks=[1],
            capture_all=True,
        )
    )
    assert result.status == ExecutionStatus.OK
    assert result.message == "Collected 1 register record(s)"
    assert data.records == [{"cpu": 0, "bank": 1}]
    assert data.stats == {"cpus_found": 1}


def test_collect_skips_when_remote(collector, monkeypatch):
    collector.system_info.location = SystemLocation.REMOTE

    def _discover(name=None, group=None):
        raise AssertionError("register tool should not be loaded for a remote system")

    monkeypatch.setattr(collector_mod, "discover_register_tool", _discover)
    result, data = collector.collect_data(RegisterDecodeCollectorArgs(tool_group="mca_tool"))
    assert result.status == ExecutionStatus.NOT_RAN
    assert data is None
    assert result.message == "Register decode is only supported on local"
    assert result.events[0].description == result.message


def test_analyze_skips_when_remote(system_info, monkeypatch):
    system_info.location = SystemLocation.REMOTE

    def _discover(name=None, group=None):
        raise AssertionError("register tool should not be loaded for a remote system")

    monkeypatch.setattr(analyzer_mod, "discover_register_tool", _discover)
    analyzer = RegisterDecodeAnalyzer(system_info=system_info)
    data = RegisterDecodeDataModel(stats={"cpus_found": 1}, records=[{"cpu": 0, "bank": 1}])
    result = analyzer.analyze_data(data, RegisterDecodeAnalyzerArgs(tool_group="mca_tool"))
    assert result.status == ExecutionStatus.NOT_RAN
    assert result.message == "Register decode is only supported on local"
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
    result, data = collector.collect_data(RegisterDecodeCollectorArgs(tool_group="mca_tool"))
    assert result.status == ExecutionStatus.ERROR
    assert data is None
    assert "Register tool health check failed" in result.message


def test_collect_reports_missing_entry_point(collector, monkeypatch):
    def _missing(name=None, group=None):
        raise RuntimeError(f"No {group} entry point is installed")

    monkeypatch.setattr(collector_mod, "discover_register_tool", _missing)
    result, data = collector.collect_data(RegisterDecodeCollectorArgs(tool_group="mca_tool"))
    assert result.status == ExecutionStatus.ERROR
    assert data is None
    assert "mca_tool" in result.message


def test_analyze_calls_decode_records(system_info, monkeypatch):
    def _discover(name=None, group=None):
        assert group == "mca_tool"
        assert name is None
        return FakeRegisterTool()

    monkeypatch.setattr(analyzer_mod, "discover_register_tool", _discover)
    analyzer = RegisterDecodeAnalyzer(system_info=system_info)
    data = RegisterDecodeDataModel(stats={"cpus_found": 1}, records=[{"cpu": 0, "bank": 1}])
    result = analyzer.analyze_data(data, RegisterDecodeAnalyzerArgs(tool_group="mca_tool"))
    assert result.status == ExecutionStatus.OK
    assert result.message == "Decoded 1 register record(s)"
