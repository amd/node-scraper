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
from __future__ import annotations

import importlib.metadata
import inspect
import json
import os
from pathlib import Path
from typing import Any, Optional

from pydantic import ValidationError

from nodescraper.models import PluginConfig

PLUGIN_CONFIG_ENTRY_POINT_GROUP = "nodescraper.plugin_configs"


class PluginConfigEntryPointError(RuntimeError):
    """Raised when a ``nodescraper.plugin_configs`` entry point cannot be loaded."""


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
    def _resolve_entry_point_config(loaded: Any) -> PluginConfig | dict[str, Any] | None:
        """Resolve a loaded entry point object into a plugin config.

        Args:
            loaded (Any): Object returned by an entry point ``load()`` call.

        Returns:
            Optional[PluginConfig | dict[str, Any]]: Plugin config, or None if ``loaded`` is unsupported.
        """
        if isinstance(loaded, PluginConfig):
            return loaded
        if isinstance(loaded, dict):
            return loaded
        if inspect.isclass(loaded) and hasattr(loaded, "plugin_config"):
            config_data = loaded.plugin_config()
        elif callable(loaded):
            config_data = loaded()
        else:
            return None

        if isinstance(config_data, (PluginConfig, dict)):
            return config_data
        return None

    @classmethod
    def load_plugin_configs_from_entry_points(cls) -> dict[str, PluginConfig]:
        """Load plugin configs registered under ``nodescraper.plugin_configs`` entry points.

        Returns:
            dict[str, PluginConfig]: Map of config name to loaded :class:`~nodescraper.models.PluginConfig`.

        Raises:
            PluginConfigEntryPointError: If an entry point target is missing, invalid, or unsupported.
        """
        configs: dict[str, PluginConfig] = {}

        for entry_point in cls._entry_points_for_group(PLUGIN_CONFIG_ENTRY_POINT_GROUP):
            entry_point_name = getattr(entry_point, "name", None)
            entry_point_label = entry_point_name or "<unknown>"
            try:
                loaded = entry_point.load()  # type: ignore[attr-defined]
                config_data = cls._resolve_entry_point_config(loaded)
                if config_data is None:
                    raise PluginConfigEntryPointError(
                        f"Failed to load plugin config entry point {entry_point_label!r}: "
                        f"unsupported target {loaded!r}"
                    )

                config_model = (
                    config_data
                    if isinstance(config_data, PluginConfig)
                    else PluginConfig(**config_data)
                )
                config_key = entry_point_name or config_model.name
                if config_key:
                    configs[config_key] = config_model
            except ModuleNotFoundError as exc:
                raise PluginConfigEntryPointError(
                    f"Failed to load plugin config entry point {entry_point_label!r}: "
                    f"module not found ({exc}). Check the entry point target in pyproject.toml."
                ) from exc
            except ValidationError as exc:
                raise PluginConfigEntryPointError(
                    f"Failed to load plugin config entry point {entry_point_label!r}: "
                    "invalid plugin config"
                ) from exc
            except PluginConfigEntryPointError:
                raise
            except Exception as exc:
                raise PluginConfigEntryPointError(
                    f"Failed to load plugin config entry point {entry_point_label!r}: {exc}"
                ) from exc

        return configs
