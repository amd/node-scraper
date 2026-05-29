###############################################################################
#
# MIT License
#
# Copyright (C) 2026 Advanced Micro Devices, Inc.
#
###############################################################################

from __future__ import annotations

from nodescraper.pluginrecipe.all_plugins import AllPlugins
from nodescraper.pluginrecipe.node_status import NodeStatus
from nodescraper.pluginregistry import PluginRegistry


def test_node_status_recipe_matches_registered_plugins() -> None:
    available = set(PluginRegistry().plugins)
    expected = {
        "BiosPlugin",
        "CmdlinePlugin",
        "DimmPlugin",
        "DkmsPlugin",
        "DmesgPlugin",
        "KernelPlugin",
        "MemoryPlugin",
        "OsPlugin",
        "RocmPlugin",
        "StoragePlugin",
        "UptimePlugin",
    }
    assert set(NodeStatus.plugin_names()) == expected & available


def test_all_plugins_recipe_matches_registry() -> None:
    plugin_reg = PluginRegistry()
    assert set(AllPlugins.plugin_names()) == set(plugin_reg.plugins)


def test_node_status_plugin_config_shape() -> None:
    config = NodeStatus.plugin_config()
    assert config["name"] == "NodeStatus"
    assert config["desc"] == "Check configuration and status of the node."
    assert isinstance(config["plugins"], dict)


def test_all_plugins_plugin_config_shape() -> None:
    config = AllPlugins.plugin_config()
    assert config["name"] == "AllPlugins"
    assert config["desc"] == "Run all registered plugins with default arguments."
    assert len(config["plugins"]) == len(PluginRegistry().plugins)
