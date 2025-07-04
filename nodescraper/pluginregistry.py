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
import importlib
import inspect
import pkgutil
import types
from typing import Optional

import nodescraper.connection as internal_connections
import nodescraper.plugins as internal_plugins
import nodescraper.resultcollators as internal_collators
from nodescraper.interfaces import (
    ConnectionManager,
    PluginInterface,
    PluginResultCollator,
)


class PluginRegistry:

    def __init__(
        self,
        plugin_pkg: Optional[list[types.ModuleType]] = None,
        load_internal_plugins: bool = True,
    ) -> None:
        """Initialize the PluginRegistry with optional plugin packages.

        Args:
            plugin_pkg (Optional[list[types.ModuleType]], optional): The module to search for plugins in. Defaults to None.
            load_internal_plugins (bool, optional): Whether internal plugin should be loaded. Defaults to True.
        """
        if load_internal_plugins:
            self.plugin_pkg = [internal_plugins, internal_connections, internal_collators]
        else:
            self.plugin_pkg = []

        if plugin_pkg:
            self.plugin_pkg += plugin_pkg

        self.plugins: dict[str, type[PluginInterface]] = PluginRegistry.load_plugins(
            PluginInterface, self.plugin_pkg
        )
        self.connection_managers: dict[str, type[ConnectionManager]] = PluginRegistry.load_plugins(
            ConnectionManager, self.plugin_pkg
        )
        self.result_collators: dict[str, type[PluginResultCollator]] = PluginRegistry.load_plugins(
            PluginResultCollator, self.plugin_pkg
        )

    @staticmethod
    def load_plugins(
        base_class: type,
        search_modules: list[types.ModuleType],
    ) -> dict[str, type]:
        """Load plugins from the specified modules that are subclasses of the given base class.

        Args:
            base_class (type): The base class that the plugins should inherit from.
            search_modules (list[types.ModuleType]): List of modules to search for plugins.

        Returns:
            dict[str, type]: A dictionary mapping plugin names to their classes.
        """
        registry = {}

        def _recurse_pkg(pkg: types.ModuleType, base_class: type) -> None:
            for _, module_name, ispkg in pkgutil.iter_modules(pkg.__path__, pkg.__name__ + "."):
                module = importlib.import_module(module_name)
                for _, plugin in inspect.getmembers(
                    module,
                    lambda x: inspect.isclass(x)
                    and issubclass(x, base_class)
                    and not inspect.isabstract(x),
                ):
                    if hasattr(plugin, "is_valid") and not plugin.is_valid():
                        continue
                    registry[plugin.__name__] = plugin
                if ispkg:
                    _recurse_pkg(module, base_class)

        for pkg in search_modules:
            _recurse_pkg(pkg, base_class)
        return registry
