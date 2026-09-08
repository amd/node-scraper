###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
#
###############################################################################
from __future__ import annotations

from nodescraper.connection.inband import InBandConnectionManager

from .discovery import PluginDiscovery
from .pluginrecipe import PluginRecipe


class AllIbPlugins(PluginRecipe):
    """Run all registered in-band plugins with default arguments."""

    @classmethod
    def plugin_names(cls) -> tuple[str, ...]:
        """Return every in-band plugin registered at runtime.

        Returns:
            tuple[str, ...]: Sorted names of all in-band plugins in the plugin registry.
        """
        discovery = PluginDiscovery()
        return tuple(
            sorted(
                name
                for name in discovery.registered_plugin_names()
                if getattr(discovery.load_plugin_class(name), "CONNECTION_TYPE", None)
                is InBandConnectionManager
            )
        )
