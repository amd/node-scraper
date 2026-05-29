###############################################################################
#
# MIT License
#
# Copyright (C) 2026 Advanced Micro Devices, Inc.
#
###############################################################################

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

from nodescraper.configregistry import PLUGIN_CONFIG_ENTRY_POINT_GROUP, ConfigRegistry
from nodescraper.models import PluginConfig


class _ExamplePluginRecipe:
    @classmethod
    def plugin_config(cls) -> dict:
        return {
            "name": "ExamplePluginRecipe",
            "desc": "Example entry-point recipe",
            "global_args": {},
            "plugins": {"ExamplePlugin": {}},
            "result_collators": {},
        }


def _example_plugin_recipe_factory() -> dict:
    return {
        "name": "CallableRecipe",
        "desc": "Callable entry-point recipe",
        "global_args": {},
        "plugins": {"CallablePlugin": {}},
        "result_collators": {},
    }


def test_load_plugin_configs_from_entry_point_class() -> None:
    entry_point = SimpleNamespace(
        name="ExamplePluginRecipe",
        load=lambda: _ExamplePluginRecipe,
    )
    with mock.patch(
        "nodescraper.configregistry.ConfigRegistry._entry_points_for_group",
        return_value=[entry_point],
    ):
        configs = ConfigRegistry.load_plugin_configs_from_entry_points()

    assert set(configs) == {"ExamplePluginRecipe"}
    assert configs["ExamplePluginRecipe"] == PluginConfig(
        name="ExamplePluginRecipe",
        desc="Example entry-point recipe",
        global_args={},
        plugins={"ExamplePlugin": {}},
        result_collators={},
    )


def test_load_plugin_configs_from_entry_point_callable() -> None:
    entry_point = SimpleNamespace(
        name="CallableRecipe",
        load=_example_plugin_recipe_factory,
    )
    with mock.patch(
        "nodescraper.configregistry.ConfigRegistry._entry_points_for_group",
        return_value=[entry_point],
    ):
        configs = ConfigRegistry.load_plugin_configs_from_entry_points()

    assert configs["CallableRecipe"].plugins == {"CallablePlugin": {}}


def test_config_registry_merges_entry_point_configs() -> None:
    entry_point = SimpleNamespace(
        name="ExamplePluginRecipe",
        load=lambda: _ExamplePluginRecipe,
    )
    with mock.patch(
        "nodescraper.configregistry.ConfigRegistry._entry_points_for_group",
        return_value=[entry_point],
    ):
        config_registry = ConfigRegistry(
            config_path="/nonexistent",
            load_entry_point_configs=True,
        )

    assert "ExamplePluginRecipe" in config_registry.configs
    assert config_registry.configs["ExamplePluginRecipe"].plugins == {"ExamplePlugin": {}}


def test_plugin_config_entry_point_group_constant() -> None:
    assert PLUGIN_CONFIG_ENTRY_POINT_GROUP == "nodescraper.plugin_configs"
