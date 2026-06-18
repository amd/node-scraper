###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
#
###############################################################################

from __future__ import annotations

from unittest.mock import patch

from nodescraper.models import PluginConfig
from nodescraper.pluginrecipe.ai_workloads_node_status import (
    AIWorkloadsNodeStatus,
    AIWorkloadsNodeStatusExtended,
)
from nodescraper.pluginrecipe.all_plugins import AllPlugins
from nodescraper.pluginrecipe.node_status import NodeStatus
from nodescraper.pluginrecipe.pluginrecipe import (
    ANALYZE_ONLY,
    COLLECT_AND_ANALYZE,
    COLLECT_ONLY,
    AnalyzerOnlyPluginRecipe,
    CollectorOnlyPluginRecipe,
    merge_plugin_configs,
)
from nodescraper.pluginregistry import PluginRegistry
from nodescraper.plugins.inband.amdsmi.analyzer_args import AmdSmiAnalyzerArgs
from nodescraper.plugins.inband.kernel_module.analyzer_args import (
    KernelModuleAnalyzerArgs,
)
from nodescraper.plugins.inband.memory.analyzer_args import MemoryAnalyzerArgs
from nodescraper.plugins.inband.package.analyzer_args import PackageAnalyzerArgs
from nodescraper.plugins.inband.pcie.analyzer_args import PcieAnalyzerArgs
from nodescraper.plugins.inband.storage.analyzer_args import StorageAnalyzerArgs


class _CollectorOnlyPlugin:
    COLLECTOR = object()


class _AnalyzerOnlyPlugin:
    ANALYZER = object()


class _BothTasksPlugin:
    COLLECTOR = object()
    ANALYZER = object()


class _CollectOnlyRecipe(CollectorOnlyPluginRecipe):
    @classmethod
    def plugin_names(cls) -> tuple[str, ...]:
        return ("DmesgPlugin",)


class _AnalyzeOnlyRecipe(AnalyzerOnlyPluginRecipe):
    @classmethod
    def plugin_names(cls) -> tuple[str, ...]:
        return ("DmesgPlugin",)


def test_ai_workloads_node_status_recipe_matches_registered_plugins() -> None:
    available = set(PluginRegistry().plugins)
    expected = {
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
    }
    assert set(AIWorkloadsNodeStatus.plugin_names()) == expected & available


def test_ai_workloads_node_status_extended_superset_and_optional_plugins() -> None:
    """Extended recipe adds NIC/network/NVMe/RDMA when those plugins are registered."""
    available = set(PluginRegistry().plugins)
    base = set(AIWorkloadsNodeStatus.plugin_names())
    ext = set(AIWorkloadsNodeStatusExtended.plugin_names())
    assert ext == base | ({"NicPlugin", "NetworkPlugin", "NvmePlugin", "RdmaPlugin"} & available)
    for name in ("NicPlugin", "NetworkPlugin", "NvmePlugin", "RdmaPlugin"):
        if name in available:
            assert name in ext


def test_ai_workloads_node_status_extended_plugin_config() -> None:
    cfg = AIWorkloadsNodeStatusExtended.plugin_config()
    assert cfg.name == "AIWorkloadsNodeStatusExtended"
    assert (
        cfg.plugins["AmdSmiPlugin"] == AIWorkloadsNodeStatus.plugin_config().plugins["AmdSmiPlugin"]
    )


def test_ai_workloads_node_status_plugin_config_shape() -> None:
    config = AIWorkloadsNodeStatus.plugin_config()
    assert config.name == "AIWorkloadsNodeStatus"
    desc = config.desc or ""
    assert "GPU" in desc or "ML" in desc
    assert isinstance(config.plugins, dict)
    assert "AmdSmiPlugin" in config.plugins
    assert "DmesgPlugin" in config.plugins

    amdsmi = config.plugins["AmdSmiPlugin"]
    AmdSmiAnalyzerArgs.model_validate(amdsmi.get("analysis_args") or {})

    pcie = config.plugins["PciePlugin"]
    PcieAnalyzerArgs.model_validate(pcie.get("analysis_args") or {})

    pkg = config.plugins["PackagePlugin"]
    PackageAnalyzerArgs.model_validate(pkg.get("collection_args") or {})
    PackageAnalyzerArgs.model_validate(pkg.get("analysis_args") or {})

    kmod = config.plugins["KernelModulePlugin"]
    KernelModuleAnalyzerArgs.model_validate(kmod.get("analysis_args") or {})

    mem = config.plugins["MemoryPlugin"]
    MemoryAnalyzerArgs.model_validate(mem.get("analysis_args") or {})

    sto = config.plugins["StoragePlugin"]
    StorageAnalyzerArgs.model_validate(sto.get("analysis_args") or {})

    assert amdsmi["analysis_args"]["check_static_data"] is True
    assert pkg["collection_args"]["enable_rocm_regex"] is True
    assert pkg["analysis_args"]["regex_match"] is True
    assert kmod["analysis_args"]["regex_filter"] == [r"amdgpu"]


def test_node_status_recipe_matches_registered_plugins() -> None:
    available = set(PluginRegistry().plugins)
    expected = {
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
    }
    assert set(NodeStatus.plugin_names()) == expected & available


def test_all_plugins_recipe_matches_registry() -> None:
    plugin_reg = PluginRegistry()
    assert set(AllPlugins.plugin_names()) == set(plugin_reg.plugins)


def test_node_status_plugin_config_shape() -> None:
    config = NodeStatus.plugin_config()
    assert config.name == "NodeStatus"
    assert config.desc == "Check configuration and status of the node."
    assert isinstance(config.plugins, dict)
    assert config.plugins["DmesgPlugin"] == COLLECT_AND_ANALYZE.as_config()


def test_all_plugins_plugin_config_shape() -> None:
    config = AllPlugins.plugin_config()
    assert config.name == "AllPlugins"
    assert config.desc == "Run all registered plugins with default arguments."
    assert len(config.plugins) == len(PluginRegistry().plugins)


def test_collector_only_recipe_sets_analysis_false() -> None:
    config = _CollectOnlyRecipe.plugin_config()
    assert config.plugins["DmesgPlugin"] == COLLECT_ONLY.as_config()


def test_analyzer_only_recipe_sets_collection_false() -> None:
    config = _AnalyzeOnlyRecipe.plugin_config()
    assert config.plugins["DmesgPlugin"] == ANALYZE_ONLY.as_config()


@patch("nodescraper.pluginrecipe.discovery.load_plugin_class")
def test_filter_plugin_names_by_task_type(mock_load_plugin_class) -> None:
    mock_load_plugin_class.side_effect = lambda name: {
        "CollectorPlugin": _CollectorOnlyPlugin,
        "AnalyzerPlugin": _AnalyzerOnlyPlugin,
        "BothPlugin": _BothTasksPlugin,
    }[name]

    class _Recipe(CollectorOnlyPluginRecipe):
        @classmethod
        def plugin_names(cls) -> tuple[str, ...]:
            return cls.filter_plugin_names(("CollectorPlugin", "AnalyzerPlugin", "BothPlugin"))

    assert _Recipe.plugin_names() == ("BothPlugin", "CollectorPlugin")


def test_merge_plugin_configs_preserves_plugin_flags() -> None:
    merged = merge_plugin_configs(
        PluginConfig(
            name="A",
            desc="a",
            plugins={"FooPlugin": COLLECT_ONLY.as_config()},
        ),
        PluginConfig(
            name="B",
            desc="b",
            plugins={"BarPlugin": ANALYZE_ONLY.as_config()},
        ),
    )
    assert merged.plugins["FooPlugin"] == COLLECT_ONLY.as_config()
    assert merged.plugins["BarPlugin"] == ANALYZE_ONLY.as_config()
