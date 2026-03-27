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
    """Dest names from :func:`~nodescraper.cli.common_args.add_nodescraper_core_arguments`."""
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
    plugin_name: str | None = None,
    *,
    map_sys_interaction_level: Optional[Callable[[str], str]] = None,
) -> argparse.Namespace:
    """Map host namespace to ``parsed_top_level`` for ``run-plugins`` (omit ``plugin_name`` for default config)."""
    data: dict[str, Any] = {}
    for dest in nodescraper_core_cli_dests():
        if hasattr(host_namespace, dest):
            data[dest] = getattr(host_namespace, dest)
    data["subcmd"] = "run-plugins"
    if plugin_name:
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
    """Run node-scraper CLI; same contract as :func:`~nodescraper.cli.main.run_cli_main` (lazy import)."""
    from nodescraper.cli.main import run_cli_main

    return run_cli_main(
        arg_input,
        parsed_top_level=parsed_top_level,
        plugin_arg_map=plugin_arg_map,
        invalid_plugins=invalid_plugins,
        extensions=extensions,
    )
