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

import pytest
from pydantic import ValidationError

from nodescraper.configregistry import (
    PLUGIN_CONFIG_ENTRY_POINT_GROUP,
    ConfigRegistry,
    PluginConfigEntryPointError,
)
from nodescraper.models import PluginConfig
from nodescraper.pluginrecipe.pluginrecipe import PluginRecipe


class _ExamplePluginRecipe(PluginRecipe):
    @classmethod
    def plugin_names(cls) -> tuple[str, ...]:
        return ("ExamplePlugin",)

    @classmethod
    def plugin_config(cls) -> PluginConfig:
        return PluginConfig(
            name="ExamplePluginRecipe",
            desc="Example entry-point recipe",
            plugins={"ExamplePlugin": {}},
        )


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


def test_load_plugin_configs_from_entry_point_uses_entry_point_name_only() -> None:
    entry_point = SimpleNamespace(
        name="NodeStatusPluginConfig",
        load=lambda: _ExamplePluginRecipe,
    )
    with mock.patch(
        "nodescraper.configregistry.ConfigRegistry._entry_points_for_group",
        return_value=[entry_point],
    ):
        configs = ConfigRegistry.load_plugin_configs_from_entry_points()

    assert set(configs) == {"NodeStatusPluginConfig"}
    assert configs["NodeStatusPluginConfig"].name == "ExamplePluginRecipe"


def test_load_plugin_configs_from_entry_point_callable() -> None:
    entry_point = SimpleNamespace(
        name="CallableRecipe",
        load=lambda: _example_plugin_recipe_factory,
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


def test_load_plugin_configs_raises_on_module_not_found() -> None:
    def _raise_module_not_found() -> None:
        raise ModuleNotFoundError("No module named 'missing.pluginrecipe'")

    entry_point = SimpleNamespace(
        name="BrokenRecipe",
        load=_raise_module_not_found,
    )
    with mock.patch(
        "nodescraper.configregistry.ConfigRegistry._entry_points_for_group",
        return_value=[entry_point],
    ):
        with pytest.raises(PluginConfigEntryPointError, match="module not found"):
            ConfigRegistry.load_plugin_configs_from_entry_points()


def test_load_plugin_configs_raises_on_unsupported_target() -> None:
    entry_point = SimpleNamespace(
        name="BrokenRecipe",
        load=lambda: "not-a-config",
    )
    with mock.patch(
        "nodescraper.configregistry.ConfigRegistry._entry_points_for_group",
        return_value=[entry_point],
    ):
        with pytest.raises(PluginConfigEntryPointError, match="unsupported target"):
            ConfigRegistry.load_plugin_configs_from_entry_points()


def test_load_plugin_configs_raises_on_invalid_config() -> None:
    entry_point = SimpleNamespace(
        name="BrokenRecipe",
        load=lambda: {"plugins": "not-a-dict"},
    )
    with mock.patch(
        "nodescraper.configregistry.ConfigRegistry._entry_points_for_group",
        return_value=[entry_point],
    ):
        with pytest.raises(PluginConfigEntryPointError, match="invalid plugin config") as exc_info:
            ConfigRegistry.load_plugin_configs_from_entry_points()

    assert isinstance(exc_info.value.__cause__, ValidationError)
