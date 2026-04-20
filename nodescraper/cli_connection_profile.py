# Copyright (C) 2026 Advanced Micro Devices, Inc. All rights reserved.
#
# Drop-in helpers for node-scraper: register neutral CLI flags and resolve host_cli_args.
# Wire into your top-level ArgumentParser and embed entrypoints as needed.

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from nodescraper.pluginregistry import PluginRegistry


def apply_host_cli_args_to_parsed_args(
    parsed_args: argparse.Namespace,
    host_ns: argparse.Namespace | None,
) -> None:
    """Copy ``sys_*`` fields from embed/profile namespace onto parsed top-level args."""
    if host_ns is None:
        return
    for attr in ("sys_name", "sys_location", "sys_sku", "sys_platform"):
        if hasattr(host_ns, attr):
            val = getattr(host_ns, attr)
            if val is not None:
                setattr(parsed_args, attr, val)


def materialize_connection_config_dict(
    parsed_args: argparse.Namespace,
    host_ns: argparse.Namespace | None,
    plugin_reg: PluginRegistry,
) -> None:
    """Set ``parsed_args.connection_config`` (plugin manager name → args) from loaded namespace.

    The entry-point loader returns a namespace that may include:

    * A ``connection_config`` dict (same shape as legacy JSON), and/or
    * Top-level keys matching registered :attr:`PluginRegistry.connection_managers` names.

    Values in ``connection_config`` win over same keys from top-level manager attributes.
    """
    if host_ns is None:
        return
    names = set(plugin_reg.connection_managers.keys())
    by_registry = {k: v for k, v in vars(host_ns).items() if k in names and v is not None}
    nested = getattr(host_ns, "connection_config", None)
    if nested is not None and isinstance(nested, dict):
        merged = {**by_registry, **nested}
    else:
        merged = by_registry or {}
    if merged:
        parsed_args.connection_config = merged


def register_connection_config_loader_arguments(parser: argparse.ArgumentParser) -> None:
    """Add ``--connection-config`` (JSON file path) and optional loader entry-point name."""
    parser.add_argument(
        "--connection-config",
        type=Path,
        metavar="PATH",
        dest="connection_config_path",
        help="JSON file loaded via ``nodescraper.connection_profile_loaders`` (host fields + optional plugin connection dict).",
    )
    parser.add_argument(
        "--connection-config-loader",
        dest="connection_config_loader",
        default="amd_error_scraper",
        help=argparse.SUPPRESS,
    )


def load_connection_config_namespace(args: Any) -> argparse.Namespace | None:
    """If ``args.connection_config_path`` is set, run the named loader and return its namespace."""
    path = getattr(args, "connection_config_path", None)
    if path is None:
        return None
    from nodescraper.connection_profile import load_connection_profile

    name = getattr(args, "connection_config_loader", "amd_error_scraper")
    loaded = load_connection_profile(Path(path), str(name))
    if not isinstance(loaded, argparse.Namespace):
        raise TypeError(
            f"Connection profile loader {name!r} must return argparse.Namespace; got {type(loaded)!r}"
        )
    return loaded
