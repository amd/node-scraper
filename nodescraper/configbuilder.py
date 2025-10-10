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
import enum
import logging
import types
from typing import Any, Optional, Type, Union

from pydantic import BaseModel

from nodescraper.interfaces import PluginInterface
from nodescraper.models import DataModel, PluginConfig
from nodescraper.pluginregistry import PluginRegistry
from nodescraper.typeutils import TypeData, TypeUtils


class ConfigBuilder:
    """Class used to dynamically generate plugin configs"""

    def __init__(self, plugin_registry: PluginRegistry, logger: Optional[logging.Logger] = None):
        self.plugin_registry = plugin_registry
        self.logger = logger if logger else logging.getLogger()

    def gen_config(self, plugin_names: list[str]) -> PluginConfig:
        """Generate a plugin config dict for a list of plugin names

        Args:
            plugin_names (list[str]): list of plugin names to include in the config

        Returns:
            dict: plugin config dict
        """
        config = PluginConfig()
        for plugin in plugin_names:
            if plugin in self.plugin_registry.plugins:
                config.plugins[plugin] = self._build_plugin_config(
                    self.plugin_registry.plugins[plugin]
                )
            else:
                self.logger.warning("No plugin found with name: %s", plugin)
        return config

    @classmethod
    def _build_plugin_config(cls, plugin_class: Type[PluginInterface]) -> dict:
        type_map = TypeUtils.get_func_arg_types(plugin_class.run, plugin_class)
        config = {}

        for arg, arg_data in type_map.items():
            cls._update_config(arg, arg_data, config)

        return config

    @classmethod
    def _update_config(cls, config_key, type_data: TypeData, config: dict):
        if config_key in ["self", "preserve_connection", "max_event_priority_level"]:
            return

        type_class_map = {
            type_class.type_class: type_class for type_class in type_data.type_classes
        }
        if types.NoneType in type_class_map:
            return

        model_arg = next(
            (
                type_class
                for type_class in type_class_map
                if (isinstance(type_class, type) and issubclass(type_class, BaseModel))
                and not issubclass(type_class, DataModel)
            ),
            None,
        )

        if model_arg:
            model_config = {}
            for attr, attr_data in TypeUtils.get_model_types(model_arg).items():
                cls._update_config(attr, attr_data, model_config)
            config[config_key] = model_config
        else:
            config[config_key] = cls._process_value(type_data.default)

    @classmethod
    def _process_value(cls, value: Any) -> Optional[Union[dict, str, int, float, list]]:
        if isinstance(value, enum.Enum):
            return value.name

        if isinstance(value, dict):
            return_dict = {}
            for key, val in value.items():
                return_dict[key] = cls._process_value(val)

        elif not isinstance(
            value,
            (
                str,
                int,
                float,
            ),
        ):
            return None

        return value
