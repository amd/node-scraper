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

_NODE_STATUS_PLUGINS = (
    "BiosPlugin",
    "CmdlinePlugin",
    "DimmPlugin",
    "DkmsPlugin",
    "DmesgPlugin",
    "KernelPlugin",
    "MemoryPlugin",
    "OsPlugin",
    "RocmPlugin",
    "StoragePlugin",
    "UptimePlugin",
)


class NodeStatus(PluginRecipe):
    """Check configuration and status of the node."""

    @classmethod
    def plugin_names(cls) -> tuple[str, ...]:
        """Return the NodeStatus plugin set resolved at runtime.

        Returns:
            tuple[str, ...]: Sorted node-status plugin names registered in the plugin registry.
        """
        return PluginDiscovery().plugin_names_matching(_NODE_STATUS_PLUGINS)
