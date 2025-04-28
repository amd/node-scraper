import importlib
import inspect
import pkgutil
import types
from typing import Optional

import errorscraper.connection as internal_connections
import errorscraper.plugins as internal_plugins
import errorscraper.resultcollators as internal_collators
from errorscraper.interfaces import (
    ConnectionManager,
    PluginInterface,
    PluginResultCollator,
)


class PluginRegistry:

    def __init__(self, plugin_pkg: Optional[list[types.ModuleType]] = None) -> None:
        self.plugin_pkg = [internal_plugins, internal_connections, internal_collators]
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
    def load_plugins(base_class, search_modules):
        registry = {}

        def _recurse_pkg(pkg: types.ModuleType, base_class):
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
