###############################################################################
#
# MIT License
#
# Copyright (C) 2026 Advanced Micro Devices, Inc.
#
###############################################################################

from __future__ import annotations

from nodescraper.cli.cli import build_parser
from nodescraper.configregistry import ConfigRegistry
from nodescraper.pluginrecipe.all_plugins import AllPlugins
from nodescraper.pluginrecipe.node_status import NodeStatus
from nodescraper.pluginregistry import PluginRegistry


def _parser():
    plugin_reg = PluginRegistry()
    config_reg = ConfigRegistry(load_entry_point_configs=False)
    for recipe in (NodeStatus, AllPlugins):
        config_reg.configs[recipe.name()] = recipe.plugin_config()
    return build_parser(plugin_reg, config_reg)[0]


def test_plugin_configs_equals_form_parses_csv() -> None:
    ns = _parser().parse_args(["--plugin-configs=NodeStatus,AllPlugins"])
    assert ns.plugin_configs == ["NodeStatus", "AllPlugins"]


def test_plugin_configs_space_separated_parses() -> None:
    ns = _parser().parse_args(["--plugin-configs", "NodeStatus,AllPlugins"])
    assert ns.plugin_configs == ["NodeStatus", "AllPlugins"]
