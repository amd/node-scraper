###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
#
###############################################################################
from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Any, Iterable

from nodescraper.models import PluginConfig


@dataclass(frozen=True)
class PluginRunFlags:
    """Collection/analysis toggles passed to nodescraper ``DataPlugin.run``."""

    collection: bool = True
    analysis: bool = True

    def as_config(self) -> dict[str, bool]:
        """Return nodescraper per-plugin config fields.

        Returns:
            dict[str, bool]: ``collection`` and ``analysis`` entries for a plugin config.
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
        """Return collection/analysis flags for one plugin.

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
        del plugin_name
        return {}

    @classmethod
    def plugin_entry(cls, plugin_name: str) -> dict[str, Any]:
        """Build the nodescraper plugin config entry for one plugin.

        Args:
            plugin_name (str): Registered plugin name.

        Returns:
            dict[str, Any]: Per-plugin config passed to node-scraper.
        """
        entry: dict[str, Any] = dict(cls.flags_for_plugin(plugin_name).as_config())
        entry.update(cls.extra_plugin_args(plugin_name))
        return entry

    @classmethod
    def plugin_config(cls) -> PluginConfig:
        """Build a node-scraper plugin config at runtime.

        Returns:
            PluginConfig: Plugin config with ``name``, ``desc``, ``global_args``,
            ``plugins``, and ``result_collators`` fields.
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
            tuple[str, ...]: Sorted names with a ``COLLECTOR`` implementation.
        """
        from .discovery import plugins_with_collector

        return plugins_with_collector(names)


class AnalyzerOnlyPluginRecipe(PluginRecipe):
    """Recipe base for analyzer-only plugin configs."""

    DEFAULT_FLAGS = ANALYZE_ONLY

    @classmethod
    def filter_plugin_names(cls, names: Iterable[str]) -> tuple[str, ...]:
        """Keep only plugins that expose an analyzer task.

        Args:
            names (Iterable[str]): Candidate plugin names.

        Returns:
            tuple[str, ...]: Sorted names with an ``ANALYZER`` implementation.
        """
        from .discovery import plugins_with_analyzer

        return plugins_with_analyzer(names)


def _coerce_plugin_config(config: PluginConfig | dict[str, Any]) -> PluginConfig:
    if isinstance(config, PluginConfig):
        return config
    return PluginConfig.model_validate(config)


def merge_plugin_configs(*configs: PluginConfig | dict[str, Any]) -> PluginConfig:
    """Merge plugin configs, combining their ``plugins`` entries.

    Args:
        *configs: Plugin configs to merge.

    Returns:
        PluginConfig: Combined config with merged ``plugins`` entries.
    """
    normalized = [_coerce_plugin_config(config) for config in configs]
    merged_plugins: dict[str, dict[str, Any]] = {}
    for config in normalized:
        merged_plugins.update(config.plugins)
    first = normalized[0] if normalized else PluginConfig()
    return PluginConfig(
        name=first.name,
        desc=first.desc,
        global_args=first.global_args,
        plugins=merged_plugins,
        result_collators=first.result_collators,
    )
