###############################################################################
#
# MIT License
#
# Copyright (C) 2026 Advanced Micro Devices, Inc.
#
###############################################################################

from __future__ import annotations

from nodescraper.models import PluginConfig


def test_plugin_config_merge_combines_plugins() -> None:
    merged = PluginConfig.merge(
        PluginConfig(
            name="A",
            desc="a",
            plugins={"FooPlugin": {"collection": True, "analysis": False}},
        ),
        PluginConfig(
            name="B",
            desc="b",
            plugins={"BarPlugin": {"collection": False, "analysis": True}},
        ),
    )
    assert merged.name == "A"
    assert merged.desc == "a"
    assert merged.plugins["FooPlugin"] == {"collection": True, "analysis": False}
    assert merged.plugins["BarPlugin"] == {"collection": False, "analysis": True}


def test_plugin_config_merge_accepts_mappings() -> None:
    merged = PluginConfig.merge(
        {
            "name": "A",
            "plugins": {"FooPlugin": {}},
        },
        PluginConfig(plugins={"BarPlugin": {}}),
    )
    assert set(merged.plugins) == {"FooPlugin", "BarPlugin"}


def test_plugin_config_coerce() -> None:
    config = PluginConfig.coerce({"name": "Example", "plugins": {"ExamplePlugin": {}}})
    assert isinstance(config, PluginConfig)
    assert config.name == "Example"
