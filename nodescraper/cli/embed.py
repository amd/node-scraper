###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
#
###############################################################################
"""Minimal API for in-process ``run-plugins`` inside another application.

- :func:`run_cli_embedded` — run node-scraper’s CLI and return an exit code (lazy-imports main).
- :func:`build_run_plugins_parsed_top_level` / :func:`nodescraper_core_cli_dests` — map a host
  namespace (built with node-scraper core ``dest`` names) into what
  :class:`~nodescraper.cli.app.NodeScraperCliApp` expects.

For attaching ``run-plugins`` subparsers to your own root parser, use
:mod:`nodescraper.cli.run_plugins_parser` (same helpers the stock CLI uses via
:mod:`~nodescraper.cli.host_integration`). Host-specific merged parsing belongs in the host
(e.g. error-scraper), using :func:`~nodescraper.cli.helper.process_args` for argv splitting.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from typing import Any, Optional

from nodescraper.cli.common_args import add_nodescraper_core_arguments
from nodescraper.cli.extension import CliExtension

__all__ = [
    "build_run_plugins_parsed_top_level",
    "nodescraper_core_cli_dests",
    "run_cli_embedded",
]

_CACHED_CORE_DESTS: frozenset[str] | None = None


def nodescraper_core_cli_dests() -> frozenset[str]:
    """Return ``dest`` names registered by :func:`~nodescraper.cli.common_args.add_nodescraper_core_arguments`."""
    global _CACHED_CORE_DESTS
    if _CACHED_CORE_DESTS is not None:
        return _CACHED_CORE_DESTS
    p = argparse.ArgumentParser(add_help=False)
    add_nodescraper_core_arguments(p)
    dests: set[str] = set()
    for action in p._actions:
        dest = getattr(action, "dest", None)
        if dest is None or dest is argparse.SUPPRESS:
            continue
        dests.add(dest)
    _CACHED_CORE_DESTS = frozenset(dests)
    return _CACHED_CORE_DESTS


def build_run_plugins_parsed_top_level(
    host_namespace: argparse.Namespace,
    plugin_name: str,
    *,
    map_sys_interaction_level: Optional[Callable[[str], str]] = None,
) -> argparse.Namespace:
    """Build *parsed_top_level* for in-process ``run-plugins``.

    Copies attributes present on *host_namespace* whose names appear in
    :func:`nodescraper_core_cli_dests`, then sets ``subcmd="run-plugins"`` and *plugin_name*.
    """
    data: dict[str, Any] = {}
    for dest in nodescraper_core_cli_dests():
        if hasattr(host_namespace, dest):
            data[dest] = getattr(host_namespace, dest)
    data["subcmd"] = "run-plugins"
    data["plugin_name"] = plugin_name
    ns = argparse.Namespace(**data)
    if map_sys_interaction_level is not None and hasattr(ns, "sys_interaction_level"):
        ns.sys_interaction_level = map_sys_interaction_level(str(ns.sys_interaction_level))
    return ns


def run_cli_embedded(
    arg_input: list[str] | None = None,
    *,
    parsed_top_level: argparse.Namespace | None = None,
    plugin_arg_map: dict[str, list[str]] | None = None,
    invalid_plugins: list[str] | None = None,
    extensions: Sequence[CliExtension] = (),
) -> int:
    """Run node-scraper’s CLI and return an exit code.

    Same contract as :func:`~nodescraper.cli.main.run_cli_main`, imported lazily so this module
    stays loadable from :mod:`~nodescraper.cli.app` without circular imports.
    """
    from nodescraper.cli.main import run_cli_main

    return run_cli_main(
        arg_input,
        parsed_top_level=parsed_top_level,
        plugin_arg_map=plugin_arg_map,
        invalid_plugins=invalid_plugins,
        extensions=extensions,
    )
