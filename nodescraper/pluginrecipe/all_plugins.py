###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
#
###############################################################################
from __future__ import annotations

from .discovery import registered_plugin_names
from .pluginrecipe import PluginRecipe


class AllPlugins(PluginRecipe):
    """Run all registered plugins with default arguments."""

    @classmethod
    def plugin_names(cls) -> tuple[str, ...]:
        """Return every plugin registered at runtime.

        Returns:
            tuple[str, ...]: Sorted names of all plugins in the plugin registry.
        """
        return registered_plugin_names()
