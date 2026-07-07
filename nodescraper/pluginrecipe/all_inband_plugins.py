###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
#
###############################################################################
from __future__ import annotations

from .discovery import PluginDiscovery
from .pluginrecipe import PluginRecipe


class AllInbandPlugins(PluginRecipe):
    """Run all registered in-band plugins with default arguments."""

    @classmethod
    def plugin_names(cls) -> tuple[str, ...]:
        """Return every in-band plugin registered at runtime.

        Returns:
            tuple[str, ...]: Sorted names of in-band plugins in the plugin registry.
        """
        return PluginDiscovery().registered_inband_plugin_names()
