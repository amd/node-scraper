###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
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

import threading
from typing import TYPE_CHECKING, Iterable, Mapping

from nodescraper.pluginregistry import default_registry

if TYPE_CHECKING:
    from nodescraper.interfaces import PluginInterface


class PluginDiscovery:
    """Allows for the discovery of plugins and their capabilities. These external plugins must be
    registered with the :class:`~nodescraper.pluginregistry.PluginRegistry` before they can be discovered.

    This class can use a cache to avoid repeated PluginRegistry lookups, which can be expensive.
    If use_cache is False, it will query the PluginRegistry each time.
    """

    _plugin_cache: Mapping[str, type[PluginInterface]] | None = None
    _cache_registry: object | None = None
    _cache_lock = threading.Lock()
    COLLECTOR_ATTRIBUTE = "COLLECTOR"
    ANALYZER_ATTRIBUTE = "ANALYZER"

    def __init__(self, use_cache: bool = True) -> None:
        """Initialize the PluginDiscovery instance.

        Args:
            use_cache: If True, cache plugin lookups to improve performance. Defaults to True.
        """
        self._use_cache = use_cache

    def _plugins(self) -> Mapping[str, type[PluginInterface]]:
        """Plugin mapping from the shared registry (kept as-is, never copied, so lazy loading is preserved)."""
        if not self._use_cache:
            return default_registry().plugins

        registry = default_registry()
        with PluginDiscovery._cache_lock:
            if (
                PluginDiscovery._plugin_cache is None
                or PluginDiscovery._cache_registry is not registry
            ):
                PluginDiscovery._plugin_cache = registry.plugins
                PluginDiscovery._cache_registry = registry
            return PluginDiscovery._plugin_cache

    def load_plugin_class(self, plugin_name: str) -> type | None:
        return self._plugins().get(plugin_name)

    def plugin_has_collector(self, plugin_name: str) -> bool:
        """Check if a plugin has a COLLECTOR attribute.

        Args:
            plugin_name: The name of the plugin to check.

        Returns:
            True if the plugin exists and has a COLLECTOR attribute, False otherwise.
        """
        plugin_class = self.load_plugin_class(plugin_name)
        return (
            plugin_class is not None
            and getattr(plugin_class, self.COLLECTOR_ATTRIBUTE, None) is not None
        )

    def plugin_has_analyzer(self, plugin_name: str) -> bool:
        """Check if a plugin has an ANALYZER attribute.

        Args:
            plugin_name: The name of the plugin to check.

        Returns:
            True if the plugin exists and has an ANALYZER attribute, False otherwise.
        """
        plugin_class = self.load_plugin_class(plugin_name)
        return (
            plugin_class is not None
            and getattr(plugin_class, self.ANALYZER_ATTRIBUTE, None) is not None
        )

    def plugins_with_collector(self, plugin_names: Iterable[str]) -> tuple[str, ...]:
        """Filter a list of plugin names to those that have a COLLECTOR attribute.

        Args:
            plugin_names: An iterable of plugin names to filter.

        Returns:
            A sorted tuple of plugin names that have a COLLECTOR attribute.
        """
        return tuple(sorted(name for name in plugin_names if self.plugin_has_collector(name)))

    def plugins_with_analyzer(self, plugin_names: Iterable[str]) -> tuple[str, ...]:
        """Filter a list of plugin names to those that have an ANALYZER attribute.

        Args:
            plugin_names: An iterable of plugin names to filter.

        Returns:
            A sorted tuple of plugin names that have an ANALYZER attribute.
        """
        return tuple(sorted(name for name in plugin_names if self.plugin_has_analyzer(name)))

    @staticmethod
    def clear_cache() -> None:
        """Clears the plugin cache, forcing future lookups to query the PluginRegistry again.

        Thread-safe: Acquires the cache lock to ensure no other thread is accessing the cache.
        """
        with PluginDiscovery._cache_lock:
            PluginDiscovery._plugin_cache = None
            PluginDiscovery._cache_registry = None

    def registered_plugin_names(self) -> tuple[str, ...]:
        """Return all plugin names known to :class:`~nodescraper.pluginregistry.PluginRegistry`.

        Returns:
            tuple[str, ...]: Sorted registered plugin names.
        """
        return tuple(sorted(self._plugins().keys()))

    def plugin_names_matching(self, names: Iterable[str]) -> tuple[str, ...]:
        """Return plugin names from ``names`` that are registered at runtime.

        Args:
            names (Iterable[str]): Candidate plugin names to filter.

        Returns:
            tuple[str, ...]: Sorted subset of ``names`` present in the plugin registry.
        """
        available = set(self.registered_plugin_names())
        return tuple(sorted(name for name in names if name in available))
