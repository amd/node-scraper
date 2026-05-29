###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
#
###############################################################################
from __future__ import annotations

from typing import Iterable


def registered_plugin_names() -> tuple[str, ...]:
    """Return all plugin names known to :class:`~nodescraper.pluginregistry.PluginRegistry`.

    Returns:
        tuple[str, ...]: Sorted registered plugin names.
    """
    from nodescraper.pluginregistry import PluginRegistry

    return tuple(sorted(PluginRegistry().plugins))


def plugin_names_matching(names: Iterable[str]) -> tuple[str, ...]:
    """Return plugin names from ``names`` that are registered at runtime.

    Args:
        names (Iterable[str]): Candidate plugin names to filter.

    Returns:
        tuple[str, ...]: Sorted subset of ``names`` present in the plugin registry.
    """
    available = set(registered_plugin_names())
    return tuple(sorted(name for name in names if name in available))
