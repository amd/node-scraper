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
import logging
import os

import pytest
from pydantic import BaseModel

from errorscraper.cli import cli, inputargtypes
from errorscraper.configregistry import ConfigRegistry
from errorscraper.enums import SystemInteractionLevel, SystemLocation
from errorscraper.models import PluginConfig, SystemInfo


def test_log_path_arg():
    assert cli.log_path_arg("test") == "test"
    assert cli.log_path_arg("none") is None


@pytest.mark.parametrize(
    "arg_input, exp_output",
    [
        ("true", True),
        ("TRUE", True),
        ("True", True),
        ("false", False),
        ("False", False),
        ("FALSE", False),
    ],
)
def test_bool_arg(arg_input, exp_output):
    assert inputargtypes.bool_arg(arg_input) == exp_output


def test_bool_arg_exception():
    with pytest.raises(argparse.ArgumentTypeError):
        inputargtypes.bool_arg("invalid")


def test_dict_arg():
    assert inputargtypes.dict_arg('{"test": 123}') == {"test": 123}
    with pytest.raises(argparse.ArgumentTypeError):
        inputargtypes.dict_arg("invalid")


def test_json_arg(framework_fixtures_path):
    assert cli.json_arg(os.path.join(framework_fixtures_path, "example.json")) == {"test": 123}
    with pytest.raises(argparse.ArgumentTypeError):
        cli.json_arg(os.path.join(framework_fixtures_path, "invalid.json"))


def test_model_arg(framework_fixtures_path):
    class TestArg(BaseModel):
        test: int

    arg_handler = cli.ModelArgHandler(TestArg)
    assert arg_handler.process_file_arg(
        os.path.join(framework_fixtures_path, "example.json")
    ) == TestArg(test=123)

    with pytest.raises(argparse.ArgumentTypeError):
        arg_handler.process_file_arg(os.path.join(framework_fixtures_path, "invalid.json"))


def test_system_info_builder():
    assert cli.get_system_info(
        argparse.Namespace(
            sys_name="test_name",
            sys_sku="test_sku",
            sys_platform="test_plat",
            sys_location="LOCAL",
            system_config=None,
        )
    ) == SystemInfo(
        name="test_name", sku="test_sku", platform="test_plat", location=SystemLocation.LOCAL
    )

    with pytest.raises(argparse.ArgumentTypeError):
        cli.get_system_info(
            argparse.Namespace(
                sys_name="test_name",
                sys_sku="test_sku",
                sys_platform="test_plat",
                sys_location="INVALID",
                system_config=None,
            )
        )


@pytest.mark.parametrize(
    "raw_arg_input, plugin_names, exp_output",
    [
        (
            ["--sys-name", "test-sys", "--sys-sku", "test-sku"],
            ["TestPlugin1", "TestPlugin2"],
            (["--sys-name", "test-sys", "--sys-sku", "test-sku"], {}),
        ),
        (
            ["--sys-name", "test-sys", "--sys-sku", "test-sku", "run-plugins", "-h"],
            ["TestPlugin1", "TestPlugin2"],
            (["--sys-name", "test-sys", "--sys-sku", "test-sku", "run-plugins", "-h"], {}),
        ),
        (
            [
                "--sys-name",
                "test-sys",
                "--sys-sku",
                "test-sku",
                "run-plugins",
                "TestPlugin1",
                "--plugin1_arg",
                "test-val1",
                "TestPlugin2",
                "--plugin2_arg",
                "test-val2",
            ],
            ["TestPlugin1", "TestPlugin2"],
            (
                ["--sys-name", "test-sys", "--sys-sku", "test-sku", "run-plugins"],
                {
                    "TestPlugin1": ["--plugin1_arg", "test-val1"],
                    "TestPlugin2": ["--plugin2_arg", "test-val2"],
                },
            ),
        ),
    ],
)
def test_process_args(raw_arg_input, plugin_names, exp_output):
    assert cli.process_args(raw_arg_input, plugin_names) == exp_output


def test_get_plugin_configs():
    with pytest.raises(argparse.ArgumentTypeError):
        cli.get_plugin_configs(
            top_level_args=argparse.Namespace(sys_interaction_level="INVALID", plugin_configs=None),
            built_in_configs={},
            parsed_plugin_args={},
            plugin_subparser_map={},
        )

    plugin_configs = cli.get_plugin_configs(
        top_level_args=argparse.Namespace(sys_interaction_level="PASSIVE", plugin_configs=None),
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

    config = cli.build_config(
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
