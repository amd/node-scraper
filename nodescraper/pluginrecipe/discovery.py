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


def load_plugin_class(plugin_name: str) -> type | None:
    """Return a registered plugin class by name.

    Args:
        plugin_name (str): Registered plugin name.

    Returns:
        type | None: Plugin class, or ``None`` if the name is not registered.
    """
    from nodescraper.pluginregistry import PluginRegistry

    return PluginRegistry().plugins.get(plugin_name)


def plugin_has_collector(plugin_name: str) -> bool:
    """Return whether the plugin exposes a collector task.

    Args:
        plugin_name (str): Registered plugin name.

    Returns:
        bool: ``True`` when the plugin class defines ``COLLECTOR``.
    """
    plugin_class = load_plugin_class(plugin_name)
    return plugin_class is not None and getattr(plugin_class, "COLLECTOR", None) is not None


def plugin_has_analyzer(plugin_name: str) -> bool:
    """Return whether the plugin exposes an analyzer task.

    Args:
        plugin_name (str): Registered plugin name.

    Returns:
        bool: ``True`` when the plugin class defines ``ANALYZER``.
    """
    plugin_class = load_plugin_class(plugin_name)
    return plugin_class is not None and getattr(plugin_class, "ANALYZER", None) is not None


def plugins_with_collector(plugin_names: Iterable[str]) -> tuple[str, ...]:
    """Filter plugin names to those that define a collector.

    Args:
        plugin_names (Iterable[str]): Candidate plugin names.

    Returns:
        tuple[str, ...]: Sorted plugin names with a ``COLLECTOR`` implementation.
    """
    return tuple(sorted(name for name in plugin_names if plugin_has_collector(name)))


def plugins_with_analyzer(plugin_names: Iterable[str]) -> tuple[str, ...]:
    """Filter plugin names to those that define an analyzer.

    Args:
        plugin_names (Iterable[str]): Candidate plugin names.

    Returns:
        tuple[str, ...]: Sorted plugin names with an ``ANALYZER`` implementation.
    """
    return tuple(sorted(name for name in plugin_names if plugin_has_analyzer(name)))
