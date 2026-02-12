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
import os

import pytest
from pydantic import BaseModel

from nodescraper.cli import inputargtypes
from nodescraper.cli.helper import get_system_info, process_args
from nodescraper.cli.inputargtypes import ModelArgHandler, json_arg, log_path_arg
from nodescraper.enums import SystemLocation
from nodescraper.models import SystemInfo


def test_log_path_arg():
    assert log_path_arg("test") == "test"
    assert log_path_arg("none") is None


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
    assert json_arg(os.path.join(framework_fixtures_path, "example.json")) == {"test": 123}
    with pytest.raises(argparse.ArgumentTypeError):
        json_arg(os.path.join(framework_fixtures_path, "invalid.json"))


def test_model_arg(framework_fixtures_path):
    class TestArg(BaseModel):
        test: int

    arg_handler = ModelArgHandler(TestArg)
    assert arg_handler.process_file_arg(
        os.path.join(framework_fixtures_path, "example.json")
    ) == TestArg(test=123)

    with pytest.raises(argparse.ArgumentTypeError):
        arg_handler.process_file_arg(os.path.join(framework_fixtures_path, "invalid.json"))


def test_system_info_builder():
    assert get_system_info(
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
        get_system_info(
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
            (["--sys-name", "test-sys", "--sys-sku", "test-sku"], {}, []),
        ),
        (
            ["--sys-name", "test-sys", "--sys-sku", "test-sku", "run-plugins", "-h"],
            ["TestPlugin1", "TestPlugin2"],
            (["--sys-name", "test-sys", "--sys-sku", "test-sku", "run-plugins", "-h"], {}, []),
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
                [],
            ),
        ),
    ],
)
def test_process_args(raw_arg_input, plugin_names, exp_output):
    assert process_args(raw_arg_input, plugin_names) == exp_output
