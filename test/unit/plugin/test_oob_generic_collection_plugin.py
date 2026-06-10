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
from nodescraper.base import InBandDataPlugin, OOBSSHDataPlugin
from nodescraper.connection.inband.inbandmanager import InBandConnectionManager
from nodescraper.pluginregistry import PluginRegistry
from nodescraper.plugins.generic_collection import (
    GenericAnalyzer,
    GenericAnalyzerArgs,
    GenericCollectionCollector,
    GenericCollectionCollectorArgs,
    GenericCollectionDataModel,
    GenericCollectionPlugin,
    GenericCollectionPluginMixin,
    OobGenericCollectionPlugin,
)


def test_generic_collection_plugins_are_valid():
    assert GenericCollectionPlugin.is_valid()
    assert OobGenericCollectionPlugin.is_valid()


def test_generic_collection_plugins_register():
    registry = PluginRegistry()
    assert "GenericCollectionPlugin" in registry.plugins
    assert "OobGenericCollectionPlugin" in registry.plugins


def test_generic_collection_plugin_mixin_wiring():
    for plugin_cls in (GenericCollectionPlugin, OobGenericCollectionPlugin):
        assert plugin_cls.DATA_MODEL is GenericCollectionDataModel
        assert plugin_cls.get_collector_classes() == (GenericCollectionCollector,)
        assert plugin_cls.COLLECTOR_ARGS is GenericCollectionCollectorArgs
        assert plugin_cls.ANALYZER is GenericAnalyzer
        assert plugin_cls.ANALYZER_ARGS is GenericAnalyzerArgs


def test_generic_collection_plugin_uses_inband_base():
    assert issubclass(GenericCollectionPlugin, InBandDataPlugin)
    assert issubclass(GenericCollectionPlugin, GenericCollectionPluginMixin)
    assert GenericCollectionPlugin.CONNECTION_TYPE is InBandConnectionManager


def test_oob_generic_collection_plugin_uses_oob_ssh_base():
    assert issubclass(OobGenericCollectionPlugin, OOBSSHDataPlugin)
    assert issubclass(OobGenericCollectionPlugin, GenericCollectionPluginMixin)
    assert OobGenericCollectionPlugin.CONNECTION_TYPE is InBandConnectionManager
    assert GenericCollectionPlugin.COLLECTOR is OobGenericCollectionPlugin.COLLECTOR
    assert GenericCollectionPlugin.ANALYZER is OobGenericCollectionPlugin.ANALYZER
