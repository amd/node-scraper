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
from nodescraper.models import PluginConfig
from nodescraper.pluginregistry import PluginRegistry


def _parser():
    plugin_reg = PluginRegistry()
    config_reg = ConfigRegistry()
    config_reg.configs["AllPlugins"] = PluginConfig(
        name="AllPlugins",
        desc="Run all registered plugins with default arguments",
        global_args={},
        plugins={name: {} for name in plugin_reg.plugins},
        result_collators={},
    )
    return build_parser(plugin_reg, config_reg)[0]


def test_plugin_configs_equals_form_parses_csv() -> None:
    ns = _parser().parse_args(["--plugin-configs=NodeStatus,AllPlugins"])
    assert ns.plugin_configs == ["NodeStatus", "AllPlugins"]


def test_plugin_configs_space_separated_parses() -> None:
    ns = _parser().parse_args(["--plugin-configs", "NodeStatus,AllPlugins"])
    assert ns.plugin_configs == ["NodeStatus", "AllPlugins"]
