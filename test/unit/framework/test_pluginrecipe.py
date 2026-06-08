###############################################################################
#
# MIT License
#
# Copyright (C) 2026 Advanced Micro Devices, Inc.
#
###############################################################################

from __future__ import annotations

from unittest.mock import patch

from nodescraper.models import PluginConfig
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
