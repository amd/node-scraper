###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
#
###############################################################################
from unittest.mock import MagicMock

from nodescraper.cli.prefer_distribution_extension import (
    PreferDistributionPluginsExtension,
)


def test_prefer_distribution_extension_updates_plugins_from_entry_points(monkeypatch) -> None:
    called: dict = {}

    def fake_load(*, group: str, prefer_distribution_names):
        called["group"] = group
        called["prefer"] = prefer_distribution_names
        return {"FooPlugin": object}

    monkeypatch.setattr(
        "nodescraper.cli.prefer_distribution_extension.load_plugin_entry_points",
        fake_load,
    )

    ext = PreferDistributionPluginsExtension(
        prefer_distribution_names=("dist-b", "dist-a"),
        entry_point_group="nodescraper.plugins",
    )
    plugin_reg = MagicMock()
    plugin_reg.plugins = {}
    config_reg = MagicMock()

    ext.prepare_registries(plugin_reg, config_reg)

    assert called["group"] == "nodescraper.plugins"
    assert called["prefer"] == ("dist-b", "dist-a")
    assert "FooPlugin" in plugin_reg.plugins
