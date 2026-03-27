###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
#
###############################################################################
"""``run-plugins`` argparse layout (top-level subcommand + per-plugin nested parsers)."""

from __future__ import annotations

import argparse
from typing import Any

from nodescraper.cli.dynamicparserbuilder import DynamicParserBuilder
from nodescraper.pluginregistry import PluginRegistry


def add_run_plugins_top_level_parser(subparsers: Any) -> argparse.ArgumentParser:
    """Add ``run-plugins`` without per-plugin nested subparsers (attach those separately)."""
    return subparsers.add_parser(
        "run-plugins",
        help="Run a series of plugins",
    )


def attach_nested_plugin_subparsers(
    run_plugin_parser: argparse.ArgumentParser,
    plugin_reg: PluginRegistry,
) -> dict[str, tuple[argparse.ArgumentParser, dict]]:
    """Add ``run-plugins <PluginName>`` nested subparsers and dynamic plugin args."""
    plugin_subparsers = run_plugin_parser.add_subparsers(
        dest="plugin_name", help="Available plugins"
    )
    plugin_subparser_map: dict[str, tuple[argparse.ArgumentParser, dict]] = {}
    for plugin_name, plugin_class in plugin_reg.plugins.items():
        plugin_subparser = plugin_subparsers.add_parser(
            plugin_name,
            help=f"Run {plugin_name} plugin",
        )
        try:
            parser_builder = DynamicParserBuilder(plugin_subparser, plugin_class)
            model_type_map = parser_builder.build_plugin_parser()
        except Exception as e:
            print(f"Exception building arg parsers for {plugin_name}: {str(e)}")  # noqa: T201
            continue
        plugin_subparser_map[plugin_name] = (plugin_subparser, model_type_map)
    return plugin_subparser_map


__all__ = [
    "add_run_plugins_top_level_parser",
    "attach_nested_plugin_subparsers",
]
