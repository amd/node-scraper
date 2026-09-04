###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
#
###############################################################################
from __future__ import annotations

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
        return PluginDiscovery().registered_plugin_names()
