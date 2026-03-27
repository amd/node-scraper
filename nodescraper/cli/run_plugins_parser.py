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

from __future__ import annotations

import argparse
from typing import Any

from nodescraper.cli.dynamicparserbuilder import DynamicParserBuilder
from nodescraper.pluginregistry import PluginRegistry


def add_run_plugins_top_level_parser(subparsers: Any) -> argparse.ArgumentParser:
    """Add top-level ``run-plugins`` subparser only."""
    return subparsers.add_parser(
        "run-plugins",
        help="Run a series of plugins",
    )


def attach_nested_plugin_subparsers(
    run_plugin_parser: argparse.ArgumentParser,
    plugin_reg: PluginRegistry,
) -> dict[str, tuple[argparse.ArgumentParser, dict]]:
    """Attach per-plugin subparsers and dynamic args under ``run-plugins``."""
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
