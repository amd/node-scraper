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
from typing import Optional

import pytest
from common.shared_utils import MockConnectionManager
from pydantic import BaseModel

from errorscraper.configbuilder import ConfigBuilder
from errorscraper.enums import ExecutionStatus
from errorscraper.interfaces import PluginInterface
from errorscraper.models import PluginResult
from errorscraper.pluginregistry import PluginRegistry


class TestModelArg(BaseModel):
    model_attr: int = 123


class TestPluginA(PluginInterface[MockConnectionManager, None]):

    CONNECTION_TYPE = MockConnectionManager

    def run(
        self,
        test_bool_arg: bool = True,
        test_str_arg: str = "test",
        test_model_arg: Optional[TestModelArg] = None,
    ):
        return PluginResult(
            source="testA",
            status=ExecutionStatus.ERROR,
        )


@pytest.fixture
def plugin_registry():
    registry = PluginRegistry()
    registry.plugins = {"TestPluginA": TestPluginA}
    registry.connection_managers = {"MockConnectionManager": MockConnectionManager}
    return registry


def test_config_builder(plugin_registry):
    config_builder = ConfigBuilder(plugin_registry)

    config = config_builder.gen_config(["TestPluginA"])

    assert config.plugins == {
        "TestPluginA": {
            "test_bool_arg": True,
            "test_str_arg": "test",
            "test_model_arg": {"model_attr": 123},
        }
    }
