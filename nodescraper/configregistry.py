###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
###############################################################################
import importlib.metadata
import inspect
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from pydantic import ValidationError

from nodescraper.constants import DEFAULT_LOGGER
from nodescraper.models import PluginConfig

PLUGIN_CONFIG_ENTRY_POINT_GROUP = "nodescraper.plugin_configs"


class ConfigRegistry:
    """Class to load json plugin configs into models"""

    INTERNAL_SEARCH_PATH = os.path.join(os.path.dirname(__file__), "configs")

    def __init__(
        self,
        config_path: Optional[str] = None,
        load_entry_point_configs: bool = True,
    ) -> None:
        """Initialize the config registry.

        Args:
            config_path (Optional[str], optional): Path in which to search for JSON config files.
                Defaults to None.
            load_entry_point_configs (bool, optional): Whether to load ``nodescraper.plugin_configs``
                entry points. Defaults to True.
        """
        self.configs: dict[str, PluginConfig] = {}
        self.load_configs(config_path)
        if load_entry_point_configs:
            self.configs.update(self.load_plugin_configs_from_entry_points())

    def load_configs(self, config_path: Optional[str] = None):
        """Load plugin config JSON files into pydantic models.

        Args:
            config_path (Optional[str], optional): Path in which to search for config files.
                Defaults to None.
        """
        if not config_path:
            config_path = self.INTERNAL_SEARCH_PATH

        config_path = Path(config_path)

        for config_file in config_path.glob("*.json"):
            with open(config_file, "r", encoding="utf-8") as in_file:
                try:
                    file_data = json.load(in_file)
                    config_model = PluginConfig(**file_data)
                    if config_model.name:
                        self.configs[config_model.name] = config_model
                    else:
                        self.configs[config_file.name] = config_model
                except (ValidationError, json.JSONDecodeError):
                    pass

    @staticmethod
    def _entry_points_for_group(group: str):
        """Return setuptools entry points for the given group name.

        Args:
            group (str): Entry point group to query.

        Returns:
            Iterable: Entry points registered under ``group``.
        """
        try:
            return importlib.metadata.entry_points(group=group)  # type: ignore[call-arg]
        except TypeError:
            all_eps = importlib.metadata.entry_points()  # type: ignore[assignment]
            return all_eps.get(group, [])  # type: ignore[assignment, attr-defined, arg-type]

    @staticmethod
    def _resolve_entry_point_config(loaded: Any) -> Optional[dict[str, Any]]:
        """Resolve a loaded entry point object into a plugin config dict.

        Args:
            loaded (Any): Object returned by an entry point ``load()`` call.

        Returns:
            Optional[dict[str, Any]]: Plugin config dict, or None if ``loaded`` is unsupported.
        """
        if isinstance(loaded, dict):
            return loaded
        if inspect.isclass(loaded) and hasattr(loaded, "plugin_config"):
            config_data = loaded.plugin_config()
        elif callable(loaded):
            config_data = loaded()
        else:
            return None

        if not isinstance(config_data, dict):
            return None
        return config_data

    @classmethod
    def load_plugin_configs_from_entry_points(cls) -> dict[str, PluginConfig]:
        """Load plugin configs registered under ``nodescraper.plugin_configs`` entry points.

        Returns:
            dict[str, PluginConfig]: Map of config name to loaded :class:`~nodescraper.models.PluginConfig`.
        """
        configs: dict[str, PluginConfig] = {}
        logger = logging.getLogger(DEFAULT_LOGGER)

        for entry_point in cls._entry_points_for_group(PLUGIN_CONFIG_ENTRY_POINT_GROUP):
            entry_point_name = getattr(entry_point, "name", "<unknown>")
            try:
                loaded = entry_point.load()  # type: ignore[attr-defined]
                config_data = cls._resolve_entry_point_config(loaded)
                if config_data is None:
                    logger.warning(
                        "Skipping plugin config entry point %r: unsupported target %r",
                        entry_point_name,
                        loaded,
                    )
                    continue

                config_model = PluginConfig(**config_data)
                if entry_point_name:
                    configs[entry_point_name] = config_model
                if config_model.name and config_model.name not in configs:
                    configs[config_model.name] = config_model
            except Exception as exc:
                logger.warning(
                    "Failed to load plugin config entry point %r: %s",
                    entry_point_name,
                    exc,
                )

        return configs
