###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
#
###############################################################################
from __future__ import annotations

import abc
from typing import Any


class PluginRecipe(abc.ABC):
    """Parent class for node-scraper plugin configuration recipes."""

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
    def plugin_config(cls) -> dict[str, Any]:
        """Build a node-scraper plugin config dict at runtime.

        Returns:
            dict[str, Any]: Plugin config payload with ``name``, ``desc``, ``global_args``,
            ``plugins``, and ``result_collators`` keys.
        """
        return {
            "name": cls.name(),
            "desc": cls.description(),
            "global_args": {},
            "plugins": {plugin_name: {} for plugin_name in cls.plugin_names()},
            "result_collators": {},
        }
