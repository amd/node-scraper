###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
#
###############################################################################
from __future__ import annotations

from .discovery import plugin_names_matching
from .pluginrecipe import PluginRecipe

_AI_WORKLOADS_NODE_STATUS_PLUGINS = (
    "AmdSmiPlugin",
    "BiosPlugin",
    "CmdlinePlugin",
    "DeviceEnumerationPlugin",
    "DimmPlugin",
    "DkmsPlugin",
    "DmesgPlugin",
    "KernelModulePlugin",
    "KernelPlugin",
    "MemoryPlugin",
    "OsPlugin",
    "PackagePlugin",
    "PciePlugin",
    "ProcessPlugin",
    "RocmPlugin",
    "StoragePlugin",
    "SysctlPlugin",
    "UptimePlugin",
)


class AIWorkloadsNodeStatus(PluginRecipe):
    """Node status plus GPU and ML workload plugins (AMD SMI, PCIe, modules, packages, sysctl, etc.)."""

    @classmethod
    def plugin_names(cls) -> tuple[str, ...]:
        """Return the AI workloads node-status plugin set resolved at runtime.

        Returns:
            tuple[str, ...]: Sorted plugin names registered in the plugin registry.
        """
        return plugin_names_matching(_AI_WORKLOADS_NODE_STATUS_PLUGINS)
