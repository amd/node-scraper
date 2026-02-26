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
import argparse
import csv
import json
import logging
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

# from common.shared_utils import DummyDataModel
from conftest import DummyDataModel
from pydantic import BaseModel

from nodescraper.cli.helper import (
    build_config,
    dump_results_to_csv,
    dump_to_csv,
    find_datamodel_and_result,
    generate_reference_config,
    generate_reference_config_from_logs,
    generate_summary,
    get_plugin_configs,
)
from nodescraper.configregistry import ConfigRegistry
from nodescraper.enums import ExecutionStatus, SystemInteractionLevel
from nodescraper.models import PluginConfig, TaskResult
from nodescraper.models.datapluginresult import DataPluginResult
from nodescraper.models.pluginresult import PluginResult
from nodescraper.pluginregistry import PluginRegistry


def test_generate_reference_config(plugin_registry):
    results = [
        PluginResult(
            status=ExecutionStatus.OK,
            source="TestPluginA",
            message="Plugin tasks completed successfully",
            result_data=DataPluginResult(
                system_data=DummyDataModel(foo="17"),
                collection_result=TaskResult(
                    status=ExecutionStatus.OK,
                    message="BIOS: 17",
                    task="BiosCollector",
                    parent="TestPluginA",
                    artifacts=[],
                ),
            ),
        )
    ]

    ref_config = generate_reference_config(results, plugin_registry, logging.getLogger())
    dump = ref_config.dict()
    assert dump["plugins"] == {"TestPluginA": {"analysis_args": {"model_attr": 17}}}


def test_get_plugin_configs():
    with pytest.raises(argparse.ArgumentTypeError):
        get_plugin_configs(
            system_interaction_level="INVALID",
            plugin_config_input=[],
            built_in_configs={},
            parsed_plugin_args={},
            plugin_subparser_map={},
        )

    plugin_configs = get_plugin_configs(
        system_interaction_level="PASSIVE",
        plugin_config_input=[],
        built_in_configs={},
        parsed_plugin_args={
            "TestPlugin1": argparse.Namespace(arg1="test123"),
            "TestPlugin2": argparse.Namespace(arg2="testabc", model_arg1="123", model_arg2="abc"),
        },
        plugin_subparser_map={
            "TestPlugin1": (argparse.ArgumentParser(), {}),
            "TestPlugin2": (
                argparse.ArgumentParser(),
                {"model_arg1": "my_model", "model_arg2": "my_model"},
            ),
        },
    )

    assert plugin_configs == [
        PluginConfig(
            global_args={"system_interaction_level": SystemInteractionLevel.PASSIVE},
            plugins={},
            result_collators={"TableSummary": {}},
        ),
        PluginConfig(
            plugins={
                "TestPlugin1": {"arg1": "test123"},
                "TestPlugin2": {
                    "arg2": "testabc",
                    "my_model": {"model_arg1": "123", "model_arg2": "abc"},
                },
            },
        ),
    ]


def test_config_builder(plugin_registry):

    config = build_config(
        config_reg=ConfigRegistry(config_path=os.path.join(os.path.dirname(__file__), "fixtures")),
        plugin_reg=plugin_registry,
        logger=logging.getLogger(),
        plugins=["TestPluginA"],
        built_in_configs=["ExampleConfig"],
    )
    assert config.plugins == {
        "TestPluginA": {
            "test_bool_arg": True,
            "test_str_arg": "test",
            "test_model_arg": {"model_attr": 123},
        },
        "ExamplePlugin": {},
    }


def test_find_datamodel_and_result_with_fixture(framework_fixtures_path):
    base_dir = framework_fixtures_path / "log_dir"
    assert (base_dir / "collector/biosdatamodel.json").exists()
    assert (base_dir / "collector/result.json").exists()

    pairs = find_datamodel_and_result(str(base_dir))
    assert len(pairs) == 1

    datamodel_path, result_path = pairs[0]
    dm = Path(datamodel_path)
    rt = Path(result_path)

    assert dm.parent == base_dir / "collector"
    assert rt.parent == base_dir / "collector"

    assert dm.name == "biosdatamodel.json"
    assert rt.name == "result.json"


def test_find_datamodel_and_result_with_plugin_reg_finds_log(tmp_path):
    """With plugin_reg, a collector dir with result.json and a .log file finds the .log."""
    collector = tmp_path / "collector"
    collector.mkdir()
    result_json = {
        "status": "OK",
        "message": "ok",
        "task": "JournalCollector",
        "parent": "JournalPlugin",
        "start_time": "2025-01-01T00:00:00",
        "end_time": "2025-01-01T00:00:01",
    }
    (collector / "result.json").write_text(json.dumps(result_json), encoding="utf-8")
    (collector / "journal.log").write_text("some log line\n", encoding="utf-8")

    plugin_reg = PluginRegistry()
    pairs = find_datamodel_and_result(str(tmp_path), plugin_reg)

    assert len(pairs) == 1
    dm_path, res_path = pairs[0]
    assert Path(dm_path).name == "journal.log"
    assert Path(res_path).name == "result.json"


def test_generate_reference_config_from_logs(framework_fixtures_path):
    logger = logging.getLogger()
    res_payload = json.loads(
        (framework_fixtures_path / "log_dir/collector/result.json").read_text(encoding="utf-8")
    )
    parent = res_payload["parent"]

    class FakeDataModel:
        @classmethod
        def model_validate(cls, payload):
            return payload

    class FakeArgs(BaseModel):
        @classmethod
        def build_from_model(cls, datamodel):
            return cls()

    plugin_reg = SimpleNamespace(
        plugins={parent: SimpleNamespace(DATA_MODEL=FakeDataModel, ANALYZER_ARGS=FakeArgs)}
    )

    cfg = generate_reference_config_from_logs(str(framework_fixtures_path), plugin_reg, logger)

    assert isinstance(cfg, PluginConfig)
    assert set(cfg.plugins) == {parent}
    assert cfg.plugins[parent]["analysis_args"] == {}


def test_dump_to_csv(tmp_path):
    logger = logging.getLogger()
    data = [
        {
            "nodename": "node1",
            "plugin": "TestPlugin",
            "status": "OK",
            "timestamp": "2025_07_16-12_00_00_PM",
            "message": "Success",
        }
    ]
    filename = tmp_path / "test.csv"
    fieldnames = list(data[0].keys())

    dump_to_csv(data, str(filename), fieldnames, logger)

    with open(filename, newline="") as f:
        reader = list(csv.DictReader(f))
        assert reader == data


def test_dump_results_to_csv(tmp_path, caplog):
    logger = logging.getLogger()

    result = PluginResult(
        source="TestPlugin", status=ExecutionStatus.OK, message="some message", result_data={}
    )

    dump_results_to_csv([result], "node123", str(tmp_path), "2025_07_16-01_00_00_PM", logger)

    out_file = tmp_path / "nodescraper.csv"
    assert out_file.exists()

    with open(out_file, newline="") as f:
        reader = list(csv.DictReader(f))
        assert reader[0]["nodename"] == "node123"
        assert reader[0]["plugin"] == "TestPlugin"
        assert reader[0]["status"] == "OK"
        assert reader[0]["message"] == "some message"


def test_generate_summary(tmp_path):
    logger = logging.getLogger()

    subdir = tmp_path / "sub"
    subdir.mkdir()

    errorscraper_path = subdir / "nodescraper.csv"
    with open(errorscraper_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["nodename", "plugin", "status", "timestamp", "message"]
        )
        writer.writeheader()
        writer.writerow(
            {
                "nodename": "nodeX",
                "plugin": "PluginA",
                "status": "OK",
                "timestamp": "2025_07_16-01_00_00_PM",
                "message": "some message",
            }
        )

    generate_summary(str(tmp_path), str(tmp_path), logger)

    summary_path = tmp_path / "summary.csv"
    assert summary_path.exists()

    with open(summary_path, newline="") as f:
        rows = list(csv.DictReader(f))
        assert len(rows) == 1
        assert rows[0]["plugin"] == "PluginA"
