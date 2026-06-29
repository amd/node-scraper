###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
#
###############################################################################

from __future__ import annotations

import abc
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict

from nodescraper.models import PluginConfig
from nodescraper.pluginrecipe.discovery import PluginDiscovery


class PluginRunFlags(BaseModel):
    model_config = ConfigDict(frozen=True)

    collection: bool = True
    analysis: bool = True

    def as_config(self) -> dict[str, bool]:
        """Return collection and analysis fields for one plugin entry.

        Returns:
            dict[str, bool]: ``collection`` and ``analysis`` entries for a plugin entry.
        """
        return {"collection": self.collection, "analysis": self.analysis}


COLLECT_ONLY = PluginRunFlags(collection=True, analysis=False)
ANALYZE_ONLY = PluginRunFlags(collection=False, analysis=True)
COLLECT_AND_ANALYZE = PluginRunFlags(collection=True, analysis=True)


class PluginRecipe(abc.ABC):
    """Parent class for node-scraper plugin configuration recipes."""

    DEFAULT_FLAGS: PluginRunFlags = COLLECT_AND_ANALYZE

    @classmethod
    @abc.abstractmethod
    def plugin_names(cls) -> tuple[str, ...]:
        """Return plugin names for this recipe.

        Returns:
            tuple[str, ...]: Registered plugin names included in this recipe.
        """

    @classmethod
    def name(cls) -> str:
        """Return the config identifier for this recipe.

        Returns:
            str: Recipe class name used as the config key.
        """
        return cls.__name__

    @classmethod
    def description(cls) -> str:
        """Return the human-readable recipe description.

        Returns:
            str: Class docstring text, or an empty string if none is set.
        """
        if cls.__doc__:
            return cls.__doc__.strip()
        return ""

    @classmethod
    def flags_for_plugin(cls, plugin_name: str) -> PluginRunFlags:
        """Return collection and analysis flags for the given plugin.

        Args:
            plugin_name (str): Registered plugin name.

        Returns:
            PluginRunFlags: Flags to embed in the plugin config entry.
        """
        return cls.DEFAULT_FLAGS

    @classmethod
    def extra_plugin_args(cls, plugin_name: str) -> dict[str, Any]:
        """Return additional per-plugin config fields beyond collection/analysis.

        Args:
            plugin_name (str): Registered plugin name.

        Returns:
            dict[str, Any]: Extra plugin config kwargs merged into the entry dict.
        """
        _plugin_name = plugin_name  # Avoid unused variable warning
        return {}

    @classmethod
    def plugin_entry(cls, plugin_name: str) -> dict[str, Any]:
        """Build the per-plugin config entry for one plugin.plugins: type[PluginInterface] | None
        Args:
            plugin_name (str): Registered plugin name.

        Returns:
            dict[str, Any]: Per-plugin config for a single plugin.
        """
        entry: dict[str, Any] = dict(cls.flags_for_plugin(plugin_name).as_config())
        entry.update(cls.extra_plugin_args(plugin_name))
        return entry

    @classmethod
    def plugin_config(cls) -> PluginConfig:
        """Build the full plugin config for this recipe.

        Returns:
            PluginConfig: Config with recipe name, description, and per-plugin entries.
        """
        return PluginConfig(
            name=cls.name(),
            desc=cls.description(),
            plugins={
                plugin_name: cls.plugin_entry(plugin_name) for plugin_name in cls.plugin_names()
            },
        )


class CollectorOnlyPluginRecipe(PluginRecipe):
    """Recipe base for collector-only plugin configs."""

    DEFAULT_FLAGS = COLLECT_ONLY

    @classmethod
    def filter_plugin_names(cls, names: Iterable[str]) -> tuple[str, ...]:
        """Keep only plugins that expose a collector task.

        Args:
            names (Iterable[str]): Candidate plugin names.

        Returns:
            tuple[str, ...]: Sorted names that implement collection.
        """

        return PluginDiscovery().plugins_with_collector(names)


class AnalyzerOnlyPluginRecipe(PluginRecipe):
    """Recipe base for analyzer-only plugin configs."""

    DEFAULT_FLAGS = ANALYZE_ONLY

    @classmethod
    def filter_plugin_names(cls, names: Iterable[str]) -> tuple[str, ...]:
        """Keep only plugins that expose an analyzer task.

        Args:
            names (Iterable[str]): Candidate plugin names.

        Returns:
            tuple[str, ...]: Sorted names that implement analysis.
        """

        return PluginDiscovery().plugins_with_analyzer(names)


def merge_plugin_configs(*configs: PluginConfig | dict[str, Any]) -> PluginConfig:
    """Merge plugin configs, combining their ``plugins`` entries.

    Args:
        *configs: Plugin configs to merge.

    Returns:
        PluginConfig: Combined config with merged ``plugins`` entries.
    """
    return PluginConfig.merge(*configs)
