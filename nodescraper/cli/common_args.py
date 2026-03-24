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
    subparser_merge_safe: bool = False,
) -> None:
    """Register core node-scraper CLI flags on *parser* (shared by main and subcommands).

    Args:
        parser: Target parser (often from a parent with ``add_help=False``).
        config_reg: If set, ``--plugin-configs`` help lists built-in config names.
        sys_interaction_level_default: Default for ``--system-interaction-level``
            / ``--sys-interaction-level``.
        sys_interaction_level_choices: Allowed names; default is names from
            :class:`~nodescraper.enums.SystemInteractionLevel`. Override with a custom list when
            the host application uses different level labels with the same parser.
        subparser_merge_safe: If True, use ``default=argparse.SUPPRESS`` for optional flags so a
            duplicate ``parents=`` on an argparse subparser does not overwrite values parsed before
            the subcommand (host apps that attach the same parent to root and ``run`` /
            ``run-plugins``).
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

    def _def(value):
        return argparse.SUPPRESS if subparser_merge_safe else value

    parser.add_argument(
        "--system-hostname",
        "--sys-name",
        dest="sys_name",
        default=_def(platform.node()),
        help="Target system hostname (same as --sys-name)",
        metavar=META_VAR_MAP[str],
    )

    parser.add_argument(
        "--system-location",
        "--sys-location",
        dest="sys_location",
        type=str.upper,
        choices=[e.name for e in SystemLocation],
        default=_def("LOCAL"),
        help="Location of target system (same as --sys-location)",
    )

    parser.add_argument(
        "--system-interaction-level",
        "--sys-interaction-level",
        dest="sys_interaction_level",
        type=str.upper,
        choices=interaction_choices,
        default=_def(sys_interaction_level_default),
        help="System interaction level (same as --sys-interaction-level)",
    )

    parser.add_argument(
        "--system-sku",
        "--sys-sku",
        dest="sys_sku",
        type=str.upper,
        required=False,
        default=_def(None),
        help="SKU of system (same as --sys-sku)",
        metavar=META_VAR_MAP[str],
    )

    parser.add_argument(
        "--system-platform",
        "--sys-platform",
        dest="sys_platform",
        type=str,
        required=False,
        default=_def(None),
        help="System platform (same as --sys-platform)",
        metavar=META_VAR_MAP[str],
    )

    parser.add_argument(
        "--plugin-configs",
        type=str,
        nargs="*",
        default=_def(None),
        help=("built-in config names or paths to plugin config JSONs." f"{builtin_configs_hint}"),
        metavar=META_VAR_MAP[str],
    )

    parser.add_argument(
        "--system-config",
        type=ModelArgHandler(SystemInfo).process_file_arg,
        required=False,
        default=_def(None),
        help="Path to system config json",
        metavar=META_VAR_MAP[str],
    )

    parser.add_argument(
        "--connection-config",
        type=json_arg,
        required=False,
        default=_def(None),
        help="Path to connection config json",
        metavar=META_VAR_MAP[str],
    )

    parser.add_argument(
        "--log-path",
        default=_def("."),
        type=log_path_arg,
        help="Specifies local path for node scraper logs, use 'None' to disable logging",
        metavar=META_VAR_MAP[str],
    )

    parser.add_argument(
        "--log-level",
        default=_def("INFO"),
        choices=logging._nameToLevel,
        help="Change python log level",
    )

    ref_skip_kw: dict = {"action": "store_true"}
    if subparser_merge_safe:
        ref_skip_kw["default"] = argparse.SUPPRESS

    parser.add_argument(
        "--gen-reference-config",
        dest="reference_config",
        help="Generate reference config from system. Writes to ./reference_config.json.",
        **ref_skip_kw,
    )

    parser.add_argument(
        "--skip-sudo",
        dest="skip_sudo",
        help="Skip plugins that require sudo permissions",
        **ref_skip_kw,
    )


def build_nodescraper_core_parent_parser(
    *,
    config_reg: Optional["ConfigRegistry"] = None,
    sys_interaction_level_default: str = "INTERACTIVE",
    sys_interaction_level_choices: Optional[list[str]] = None,
    subparser_merge_safe: bool = False,
) -> argparse.ArgumentParser:
    """Return ``ArgumentParser(add_help=False)`` with core node-scraper arguments."""
    p = argparse.ArgumentParser(add_help=False)
    add_nodescraper_core_arguments(
        p,
        config_reg=config_reg,
        sys_interaction_level_default=sys_interaction_level_default,
        sys_interaction_level_choices=sys_interaction_level_choices,
        subparser_merge_safe=subparser_merge_safe,
    )
    return p
