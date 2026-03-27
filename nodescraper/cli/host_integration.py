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
"""Low-level argparse composition for the node-scraper CLI."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import nodescraper
from nodescraper.cli.common_args import (
    add_nodescraper_core_arguments,
    build_nodescraper_core_parent_parser,
)
from nodescraper.cli.extension import CliExtension
from nodescraper.cli.inputargtypes import log_path_arg
from nodescraper.cli.run_plugins_parser import (
    add_run_plugins_top_level_parser,
    attach_nested_plugin_subparsers,
)

if TYPE_CHECKING:
    from nodescraper.configregistry import ConfigRegistry
    from nodescraper.pluginregistry import PluginRegistry


__all__ = [
    "add_nodescraper_core_arguments",
    "add_run_plugins_top_level_parser",
    "attach_nested_plugin_subparsers",
    "build_nodescraper_core_parent_parser",
    "register_compare_runs_subparser",
    "register_describe_subparser",
    "add_gen_plugin_config_remaining_arguments",
    "register_gen_plugin_config_subparser_partial",
    "register_show_redfish_oem_allowable_subparser",
    "register_summary_subparser",
    "build_cli_parser",
]


def register_summary_subparser(subparsers: Any) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "summary",
        help="Generates summary csv file",
    )
    p.add_argument(
        "--search-path",
        dest="search_path",
        type=log_path_arg,
        help="Path to node-scraper previously generated results.",
    )
    p.add_argument(
        "--output-path",
        dest="output_path",
        type=log_path_arg,
        help="Specifies path for summary.csv.",
    )
    return p


def register_describe_subparser(subparsers: Any) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "describe",
        help="Display details on a built-in config or plugin",
    )
    p.add_argument(
        "type",
        choices=["config", "plugin"],
        help="Type of object to describe (config or plugin)",
    )
    p.add_argument(
        "name",
        nargs="?",
        help="Name of the config or plugin to describe",
    )
    return p


def register_gen_plugin_config_subparser_partial(subparsers: Any) -> argparse.ArgumentParser:
    """Create ``gen-plugin-config`` and the first flag only (matches legacy build order)."""
    p = subparsers.add_parser(
        "gen-plugin-config",
        help="Generate a config for a plugin or list of plugins",
    )
    p.add_argument(
        "--gen-reference-config-from-logs",
        dest="reference_config_from_logs",
        type=log_path_arg,
        help="Generate reference config from previous run logfiles. Writes to --output-path/reference_config.json if provided, otherwise ./reference_config.json.",
    )
    return p


def add_gen_plugin_config_remaining_arguments(
    config_builder_parser: argparse.ArgumentParser,
    plugin_reg: PluginRegistry,
    config_reg: ConfigRegistry,
) -> None:
    """Remaining ``gen-plugin-config`` flags (after compare-runs / show-redfish registration)."""
    config_builder_parser.add_argument(
        "--plugins",
        nargs="*",
        choices=list(plugin_reg.plugins.keys()),
        help="Plugins to generate config for",
    )
    config_builder_parser.add_argument(
        "--built-in-configs",
        nargs="*",
        choices=list(config_reg.configs.keys()),
        help="Built in config names",
    )
    config_builder_parser.add_argument(
        "--output-path",
        default=os.getcwd(),
        help="Directory to store config",
    )
    config_builder_parser.add_argument(
        "--config-name",
        default="plugin_config.json",
        help="Name of config file",
    )


def register_compare_runs_subparser(
    subparsers: Any, plugin_reg: PluginRegistry
) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "compare-runs",
        help="Compare datamodels from two run log directories",
    )
    p.add_argument(
        "path1",
        type=str,
        help="Path to first run log directory",
    )
    p.add_argument(
        "path2",
        type=str,
        help="Path to second run log directory",
    )
    p.add_argument(
        "--skip-plugins",
        nargs="*",
        choices=list(plugin_reg.plugins.keys()),
        metavar="PLUGIN",
        help="Plugin names to exclude from comparison",
    )
    p.add_argument(
        "--include-plugins",
        nargs="*",
        choices=list(plugin_reg.plugins.keys()),
        metavar="PLUGIN",
        help="If set, only compare data for these plugins (default: compare all found)",
    )
    p.add_argument(
        "--dont-truncate",
        action="store_true",
        dest="dont_truncate",
        help="Do not truncate the Message column; show full error text and all errors (not just first 3)",
    )
    return p


def register_show_redfish_oem_allowable_subparser(subparsers: Any) -> argparse.ArgumentParser:
    p = subparsers.add_parser(
        "show-redfish-oem-allowable",
        help="Fetch OEM diagnostic allowable types from Redfish LogService (for oem_diagnostic_types_allowable)",
    )
    p.add_argument(
        "--log-service-path",
        required=True,
        help="Redfish path to LogService (e.g. redfish/v1/Systems/UBB/LogServices/DiagLogs)",
    )
    return p


def build_cli_parser(
    plugin_reg: PluginRegistry,
    config_reg: ConfigRegistry,
    *,
    extensions: Sequence[CliExtension] = (),
) -> tuple[argparse.ArgumentParser, dict[str, tuple[argparse.ArgumentParser, dict]]]:
    """Compose the node-scraper CLI :class:`argparse.ArgumentParser` and plugin subparser map.

    *extensions* receive :meth:`~nodescraper.cli.extension.CliExtension.alter_cli_parser` after
    nested plugin subparsers are attached (add host-specific flags, etc.).
    """
    core_parent = build_nodescraper_core_parent_parser(config_reg=config_reg)

    parser = argparse.ArgumentParser(
        description="node scraper CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        parents=[core_parent],
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {nodescraper.__version__}",
    )

    subparsers = parser.add_subparsers(dest="subcmd", help="Subcommands")
    subparsers.default = "run-plugins"

    register_summary_subparser(subparsers)
    run_plugin_parser = add_run_plugins_top_level_parser(subparsers)
    register_describe_subparser(subparsers)
    config_builder_parser = register_gen_plugin_config_subparser_partial(subparsers)
    register_compare_runs_subparser(subparsers, plugin_reg)
    register_show_redfish_oem_allowable_subparser(subparsers)
    add_gen_plugin_config_remaining_arguments(config_builder_parser, plugin_reg, config_reg)

    plugin_subparser_map = attach_nested_plugin_subparsers(run_plugin_parser, plugin_reg)
    for ext in extensions:
        ext.alter_cli_parser(
            root_parser=parser,
            subparsers=subparsers,
            run_plugins_parser=run_plugin_parser,
            plugin_reg=plugin_reg,
            config_reg=config_reg,
            plugin_subparser_map=plugin_subparser_map,
        )
    return parser, plugin_subparser_map
