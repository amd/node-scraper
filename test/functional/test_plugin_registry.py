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
"""Functional tests for plugin registry and plugin loading."""

import inspect

from nodescraper.pluginregistry import PluginRegistry


def test_plugin_registry_loads_plugins():
    """Test that PluginRegistry successfully loads built-in plugins."""
    registry = PluginRegistry()

    assert len(registry.plugins) > 0
    plugin_names = [name.lower() for name in registry.plugins.keys()]
    expected_plugins = ["biosplugin", "kernelplugin", "osplugin"]

    for expected in expected_plugins:
        assert expected in plugin_names


def test_plugin_registry_has_connection_managers():
    """Test that PluginRegistry loads connection managers."""
    registry = PluginRegistry()

    assert len(registry.connection_managers) > 0
    conn_names = [name.lower() for name in registry.connection_managers.keys()]
    assert "inbandconnectionmanager" in conn_names


def test_plugin_registry_list_plugins():
    """Test that PluginRegistry stores plugins in a dictionary."""
    registry = PluginRegistry()
    plugin_dict = registry.plugins

    assert isinstance(plugin_dict, dict)
    assert len(plugin_dict) > 0
    assert all(isinstance(name, str) for name in plugin_dict.keys())
    assert all(inspect.isclass(cls) for cls in plugin_dict.values())


def test_plugin_registry_get_plugin():
    """Test that PluginRegistry can retrieve a specific plugin."""
    registry = PluginRegistry()
    plugin_names = list(registry.plugins.keys())
    assert len(plugin_names) > 0

    first_plugin_name = plugin_names[0]
    plugin = registry.plugins[first_plugin_name]

    assert plugin is not None
    assert hasattr(plugin, "run")
