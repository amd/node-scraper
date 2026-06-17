###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
#
###############################################################################
"""Plugin recipe for GPU / AI workload nodes (benchmarks, training, LLM serving)."""

from __future__ import annotations

from .discovery import plugin_names_matching
from .pluginrecipe import PluginRecipe

# NodeStatus baseline (OS, boot, dmesg, ROCm path, memory, storage, uptime) plus
# GPU/ML-focused collectors commonly needed when accelerators are under sustained load.
_AI_WORKLOADS_NODE_PLUGINS = (
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
    """In-band profile for GPU/ML nodes: OS health, AMDGPU/ROCm, PCIe, dmesg (RAS/throttle), processes, packages, GPU enumeration, and sysctl signals relevant to sustained AI workloads."""

    @classmethod
    def plugin_names(cls) -> tuple[str, ...]:
        """Return the AI workloads plugin set resolved at runtime.

        Returns:
            tuple[str, ...]: Sorted plugin names registered in the plugin registry.
        """
        return plugin_names_matching(_AI_WORKLOADS_NODE_PLUGINS)
