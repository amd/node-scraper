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
import pytest
from common.shared_utils import MockConnectionManager

from errorscraper.enums import ExecutionStatus
from errorscraper.interfaces import PluginInterface
from errorscraper.models import PluginConfig, PluginResult
from errorscraper.pluginexecutor import PluginExecutor
from errorscraper.pluginregistry import PluginRegistry


class TestPluginA(PluginInterface[MockConnectionManager, None]):

    CONNECTION_TYPE = MockConnectionManager

    def run(self):
        self._update_queue(("TestPluginB", {}))
        return PluginResult(
            source="testA",
            status=ExecutionStatus.ERROR,
        )


class TestPluginB(PluginInterface[MockConnectionManager, None]):

    CONNECTION_TYPE = MockConnectionManager

    def run(self, test_arg=None):
        return PluginResult(
            source="testB", status=ExecutionStatus.OK, result_data={"arg_val": test_arg}
        )


@pytest.fixture
def plugin_registry():
    registry = PluginRegistry()
    registry.plugins = {"TestPluginA": TestPluginA, "TestPluginB": TestPluginB}
    registry.connection_managers = {"MockConnectionManager": MockConnectionManager}
    return registry


@pytest.mark.parametrize(
    "input_configs, output_config",
    [
        (
            [
                PluginConfig(plugins={"Plugin1": {}}),
                PluginConfig(plugins={"Plugin2": {}}),
            ],
            PluginConfig(plugins={"Plugin1": {}, "Plugin2": {}}),
        ),
        (
            [
                PluginConfig(plugins={"Plugin1": {"arg1": "val1", "argA": "valA"}}),
                PluginConfig(plugins={"Plugin1": {"arg1": "val2"}}),
            ],
            PluginConfig(plugins={"Plugin1": {"arg1": "val2"}}),
        ),
        (
            [
                PluginConfig(global_args={"test": 123}),
                PluginConfig(global_args={"test1": "abc"}),
            ],
            PluginConfig(global_args={"test": 123, "test1": "abc"}),
        ),
    ],
)
def test_config_merge(input_configs: list[PluginConfig], output_config: PluginConfig):
    assert PluginExecutor._merge_configs(input_configs) == output_config


def test_plugin_queue(plugin_registry):
    executor = PluginExecutor(
        plugin_configs=[PluginConfig(global_args={"test_arg": "abc"}, plugins={"TestPluginB": {}})],
        plugin_registry=plugin_registry,
    )

    results = executor.run_queue()

    assert len(results) == 1
    assert results[0].source == "testB"
    assert results[0].status == ExecutionStatus.OK
    assert results[0].result_data == {"arg_val": "abc"}


def test_queue_callback(plugin_registry):
    executor = PluginExecutor(
        plugin_configs=[PluginConfig(plugins={"TestPluginA": {}})], plugin_registry=plugin_registry
    )

    results = executor.run_queue()

    assert len(results) == 2
    assert results[0].source == "testA"
    assert results[0].status == ExecutionStatus.ERROR
    assert results[1].source == "testB"
    assert results[1].status == ExecutionStatus.OK
