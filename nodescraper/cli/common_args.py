###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
#
###############################################################################

from __future__ import annotations

import argparse
import logging
import platform
from typing import TYPE_CHECKING, Optional

from nodescraper.cli.constants import META_VAR_MAP
from nodescraper.cli.inputargtypes import ModelArgHandler, json_arg, log_path_arg
from nodescraper.enums import SystemInteractionLevel, SystemLocation
from nodescraper.models import SystemInfo

if TYPE_CHECKING:
    from nodescraper.configregistry import ConfigRegistry


def add_nodescraper_core_arguments(
    parser: argparse.ArgumentParser,
    *,
    config_reg: Optional["ConfigRegistry"] = None,
    sys_interaction_level_default: str = "INTERACTIVE",
    sys_interaction_level_choices: Optional[list[str]] = None,
) -> None:
    """Register core node-scraper CLI flags on *parser* (shared by main and subcommands).

    Args:
        parser: Target parser (often from a parent with ``add_help=False``).
        config_reg: If set, ``--plugin-configs`` help lists built-in config names.
        sys_interaction_level_default: Default for ``--system-interaction-level``
            / ``--sys-interaction-level``.
        sys_interaction_level_choices: Allowed names; default is node-scraper's
            :class:`~nodescraper.enums.SystemInteractionLevel`. Pass a custom list
    """
    interaction_choices = (
        sys_interaction_level_choices
        if sys_interaction_level_choices is not None
        else [e.name for e in SystemInteractionLevel]
    )
    builtin_configs_hint = (
        f"\nAvailable built-in configs: {', '.join(config_reg.configs.keys())}"
        if config_reg is not None
        else ""
    )

    parser.add_argument(
        "--system-hostname",
        "--sys-name",
        dest="sys_name",
        default=platform.node(),
        help="Target system hostname (same as --sys-name)",
        metavar=META_VAR_MAP[str],
    )

    parser.add_argument(
        "--system-location",
        "--sys-location",
        dest="sys_location",
        type=str.upper,
        choices=[e.name for e in SystemLocation],
        default="LOCAL",
        help="Location of target system (same as --sys-location)",
    )

    parser.add_argument(
        "--system-interaction-level",
        "--sys-interaction-level",
        dest="sys_interaction_level",
        type=str.upper,
        choices=interaction_choices,
        default=sys_interaction_level_default,
        help="System interaction level (same as --sys-interaction-level)",
    )

    parser.add_argument(
        "--system-sku",
        "--sys-sku",
        dest="sys_sku",
        type=str.upper,
        required=False,
        help="SKU of system (same as --sys-sku)",
        metavar=META_VAR_MAP[str],
    )

    parser.add_argument(
        "--system-platform",
        "--sys-platform",
        dest="sys_platform",
        type=str,
        required=False,
        help="System platform (same as --sys-platform)",
        metavar=META_VAR_MAP[str],
    )

    parser.add_argument(
        "--plugin-configs",
        type=str,
        nargs="*",
        help=("built-in config names or paths to plugin config JSONs." f"{builtin_configs_hint}"),
        metavar=META_VAR_MAP[str],
    )

    parser.add_argument(
        "--system-config",
        type=ModelArgHandler(SystemInfo).process_file_arg,
        required=False,
        help="Path to system config json",
        metavar=META_VAR_MAP[str],
    )

    parser.add_argument(
        "--connection-config",
        type=json_arg,
        required=False,
        help="Path to connection config json",
        metavar=META_VAR_MAP[str],
    )

    parser.add_argument(
        "--log-path",
        default=".",
        type=log_path_arg,
        help="Specifies local path for node scraper logs, use 'None' to disable logging",
        metavar=META_VAR_MAP[str],
    )

    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=logging._nameToLevel,
        help="Change python log level",
    )

    parser.add_argument(
        "--gen-reference-config",
        dest="reference_config",
        action="store_true",
        help="Generate reference config from system. Writes to ./reference_config.json.",
    )

    parser.add_argument(
        "--skip-sudo",
        dest="skip_sudo",
        action="store_true",
        help="Skip plugins that require sudo permissions",
    )


def build_nodescraper_core_parent_parser(
    *,
    config_reg: Optional["ConfigRegistry"] = None,
    sys_interaction_level_default: str = "INTERACTIVE",
    sys_interaction_level_choices: Optional[list[str]] = None,
) -> argparse.ArgumentParser:
    """Return ``ArgumentParser(add_help=False)`` with core node-scraper arguments.

    Pass as ``parents=[build_nodescraper_core_parent_parser(...)]`` when building
    a main parser or subparser so users may place global flags after subcommands.
    """
    p = argparse.ArgumentParser(add_help=False)
    add_nodescraper_core_arguments(
        p,
        config_reg=config_reg,
        sys_interaction_level_default=sys_interaction_level_default,
        sys_interaction_level_choices=sys_interaction_level_choices,
    )
    return p
