###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
#
###############################################################################
"""Stable CLI hooks for embedding node-scraper in other applications.

Bump *HOST_CLI_API* when adding or changing symbols that downstream hosts rely on.
Native ``nodescraper`` ``main`` composes the same registrars via :func:`build_cli_parser`.
"""

from __future__ import annotations

import argparse
import os
from typing import TYPE_CHECKING, Any

import nodescraper
from nodescraper.cli.common_args import (
    add_nodescraper_core_arguments,
    build_nodescraper_core_parent_parser,
)
from nodescraper.cli.dynamicparserbuilder import DynamicParserBuilder
from nodescraper.cli.inputargtypes import log_path_arg

if TYPE_CHECKING:
    from nodescraper.configregistry import ConfigRegistry
    from nodescraper.pluginregistry import PluginRegistry

HOST_CLI_API = 1


__all__ = [
    "HOST_CLI_API",
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


def add_run_plugins_top_level_parser(subparsers: Any) -> argparse.ArgumentParser:
    """Add ``run-plugins`` without per-plugin nested subparsers (attach those separately)."""
    return subparsers.add_parser(
        "run-plugins",
        help="Run a series of plugins",
    )


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
) -> tuple[argparse.ArgumentParser, dict[str, tuple[argparse.ArgumentParser, dict]]]:
    """Compose the native node-scraper CLI parser (same result as legacy ``build_parser``)."""
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
    return parser, plugin_subparser_map


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
