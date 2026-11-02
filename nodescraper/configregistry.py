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
from collections.abc import Callable, Iterator, MutableMapping
from pathlib import Path
from typing import Any, Optional

from pydantic import ValidationError

from nodescraper.models import PluginConfig

PLUGIN_CONFIG_ENTRY_POINT_GROUP = "nodescraper.plugin_configs"


class PluginConfigEntryPointError(RuntimeError):
    """Raised when a ``nodescraper.plugin_configs`` entry point cannot be loaded."""


class LazyConfigMapping(MutableMapping):
    """Config name to :class:`PluginConfig` mapping that builds each config on first access.

    Listing names never runs a loader, so recipes that inspect every plugin are not
    evaluated until their config is actually requested.
    """

    def __init__(self) -> None:
        self._values: dict[str, PluginConfig] = {}
        self._loaders: dict[str, Callable[[], PluginConfig]] = {}

    def add_loader(self, name: str, loader: Callable[[], PluginConfig]) -> None:
        self._values.pop(name, None)
        self._loaders[name] = loader

    def __getitem__(self, name: str) -> PluginConfig:
        if name in self._values:
            return self._values[name]
        loader = self._loaders.get(name)
        if loader is None:
            raise KeyError(name)
        self._values[name] = loader()
        return self._values[name]

    def __setitem__(self, name: str, value: PluginConfig) -> None:
        self._loaders.pop(name, None)
        self._values[name] = value

    def __delitem__(self, name: str) -> None:
        if name not in self._values and name not in self._loaders:
            raise KeyError(name)
        self._values.pop(name, None)
        self._loaders.pop(name, None)

    def __contains__(self, name: object) -> bool:
        return name in self._values or name in self._loaders

    def __iter__(self) -> Iterator[str]:
        return iter([*self._values, *(n for n in self._loaders if n not in self._values)])

    def __len__(self) -> int:
        return len(self._values) + sum(1 for n in self._loaders if n not in self._values)


class ConfigRegistry:
    """Class to load json plugin configs into models"""

    INTERNAL_SEARCH_PATH = os.path.join(os.path.dirname(__file__), "configs")

    def __init__(
        self,
        config_path: Optional[str] = None,
        load_entry_point_configs: bool = True,
        lazy_entry_point_configs: bool = False,
    ) -> None:
        """Initialize the config registry.

        Args:
            config_path (Optional[str], optional): Path in which to search for JSON config files.
                Defaults to None.
            load_entry_point_configs (bool, optional): Whether to load ``nodescraper.plugin_configs``
                entry points. Defaults to True.
            lazy_entry_point_configs (bool, optional): If True, entry-point configs are loaded (and
                their recipes evaluated) only when first accessed by name. Load errors then surface
                at access time instead of construction. Defaults to False.
        """
        self.configs: MutableMapping[str, PluginConfig]
        if lazy_entry_point_configs:
            self.configs = LazyConfigMapping()
        else:
            self.configs = {}
        self.load_configs(config_path)
        if load_entry_point_configs:
            if lazy_entry_point_configs:
                assert isinstance(self.configs, LazyConfigMapping)
                for entry_point in self._entry_points_for_group(PLUGIN_CONFIG_ENTRY_POINT_GROUP):
                    name = getattr(entry_point, "name", None)
                    if name:
                        self.configs.add_loader(
                            name,
                            lambda ep=entry_point: self._load_entry_point_config(ep)[1],
                        )
            else:
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
            try:
                with open(config_file, "r", encoding="utf-8") as in_file:
                    try:
                        file_data = json.load(in_file)
                        config_model = PluginConfig(**file_data)
                        if config_model.name:
                            self.configs[config_model.name] = config_model
                        else:
                            self.configs[config_file.name] = config_model
                    except (ValidationError, json.JSONDecodeError, TypeError) as e:
                        raise RuntimeError(f"Failed to load config from {config_file}: {e}") from e
            except (OSError, IOError, FileNotFoundError) as e:
                raise RuntimeError(f"Failed to open config file {config_file}") from e

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
    def _resolve_entry_point_config(
        loaded: Any,
    ) -> PluginConfig | dict[str, Any] | None:
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
    def _load_entry_point_config(cls, entry_point: Any) -> tuple[Optional[str], PluginConfig]:
        """Load one ``nodescraper.plugin_configs`` entry point.

        Returns:
            tuple[Optional[str], PluginConfig]: Config key (entry-point name, else config name) and model.

        Raises:
            PluginConfigEntryPointError: If the entry point target is missing, invalid, or unsupported.
        """
        entry_point_name = getattr(entry_point, "name", None)
        entry_point_label = entry_point_name or "<unknown>"
        try:
            loaded = entry_point.load()
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
            return entry_point_name or config_model.name, config_model
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
            config_key, config_model = cls._load_entry_point_config(entry_point)
            if config_key:
                configs[config_key] = config_model

        return configs
