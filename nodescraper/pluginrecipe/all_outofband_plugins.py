###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
#
###############################################################################
from __future__ import annotations

from .band_plugin_names import registered_plugin_names_for_band
from .pluginrecipe import PluginRecipe


class AllOutofbandPlugins(PluginRecipe):
    """Run all registered out-of-band plugins with default arguments."""

    @classmethod
    def plugin_names(cls) -> tuple[str, ...]:
        """Return every out-of-band plugin registered at runtime.

        Returns:
            tuple[str, ...]: Sorted names of out-of-band plugins in the plugin registry.
        """
        return registered_plugin_names_for_band(1)
