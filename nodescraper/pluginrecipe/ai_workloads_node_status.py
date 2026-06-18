###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
#
###############################################################################
from __future__ import annotations

from typing import Any

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

# Optional plugins for multi-node / NVMe scratch (included when registered).
_AI_WORKLOADS_EXTENDED_PLUGINS = (
    "NicPlugin",
    "NetworkPlugin",
    "NvmePlugin",
    "RdmaPlugin",
)

_AI_WORKLOADS_NODE_STATUS_EXTENDED_PLUGINS = (
    *_AI_WORKLOADS_NODE_STATUS_PLUGINS,
    *_AI_WORKLOADS_EXTENDED_PLUGINS,
)


class AIWorkloadsNodeStatus(PluginRecipe):
    """Node status plus GPU and ML workload plugins (AMD SMI, PCIe, modules, packages, sysctl, etc.).

    Baseline ``analysis_args`` / ``collection_args`` tighten checks for typical ROCm AI nodes;
    override via :func:`~nodescraper.pluginrecipe.pluginrecipe.merge_plugin_configs` or a JSON
    config for fleet-specific SKU, cmdline, and memory/disk budgets. Cmdline expectations are
    not set here because they vary by image and boot policy.
    """

    @classmethod
    def plugin_names(cls) -> tuple[str, ...]:
        """Return the AI workloads node-status plugin set resolved at runtime.

        Returns:
            tuple[str, ...]: Sorted plugin names registered in the plugin registry.
        """
        return plugin_names_matching(_AI_WORKLOADS_NODE_STATUS_PLUGINS)

    @classmethod
    def extra_plugin_args(cls, plugin_name: str) -> dict[str, Any]:
        """Default per-plugin args: stronger validation for GPU/ROCm workload nodes."""
        return _ai_workloads_extra_plugin_args(plugin_name)


class AIWorkloadsNodeStatusExtended(PluginRecipe):
    """Like :class:`AIWorkloadsNodeStatus` plus NIC, host network, NVMe, and RDMA collection.

    Use this recipe when nodes participate in distributed training
    """

    @classmethod
    def plugin_names(cls) -> tuple[str, ...]:
        return plugin_names_matching(_AI_WORKLOADS_NODE_STATUS_EXTENDED_PLUGINS)

    @classmethod
    def extra_plugin_args(cls, plugin_name: str) -> dict[str, Any]:
        return _ai_workloads_extra_plugin_args(plugin_name)


def _ai_workloads_extra_plugin_args(plugin_name: str) -> dict[str, Any]:
    if plugin_name == "AmdSmiPlugin":
        return {
            "analysis_args": {
                "check_static_data": True,
                "l0_to_recovery_count_error_threshold": 3,
                "l0_to_recovery_count_warning_threshold": 1,
            }
        }
    if plugin_name == "PciePlugin":
        return {
            "analysis_args": {
                "exp_speed": 5,
                "exp_width": 16,
            }
        }
    if plugin_name == "PackagePlugin":
        return {
            "collection_args": {
                "enable_rocm_regex": True,
                "rocm_regex": r"rocm|hip|hsa|amdgpu|miopen|comgr|rocblas|hipblas",
            },
            "analysis_args": {
                "regex_match": True,
                "exp_package_ver": {
                    r"(?i).*(rocm-core|hip-runtime|hsa-rocr|amdgpu-dkms).*": None,
                },
            },
        }
    if plugin_name == "KernelModulePlugin":
        return {
            "analysis_args": {
                "regex_filter": [r"amdgpu"],
            }
        }
    if plugin_name == "MemoryPlugin":
        return {
            "analysis_args": {
                "ratio": 0.62,
                "memory_threshold": "32Gi",
            }
        }
    if plugin_name == "StoragePlugin":
        return {
            "analysis_args": {
                "min_required_free_space_prct": 12,
                "ignore_devices": ["snapfuse", "tmpfs"],
            }
        }
    return {}
