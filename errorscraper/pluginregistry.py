import importlib
import inspect
import pkgutil
import types
from typing import Optional

import errorscraper.connection as internal_connections
import errorscraper.plugins as internal_plugins
from errorscraper.interfaces.connectionmanager import ConnectionManager
from errorscraper.interfaces.plugin import PluginInterface


class PluginRegistry:

    def __init__(self, plugin_pkg: Optional[list[types.ModuleType]] = None) -> None:
        self.plugin_pkg = [internal_plugins, internal_connections]
        if plugin_pkg:
            self.plugin_pkg += plugin_pkg

        self.plugins: dict[str, type[PluginInterface]] = self.load_plugins(PluginInterface)
        self.connection_managers: dict[str, type[ConnectionManager]] = self.load_plugins(
            ConnectionManager
        )

    def load_plugins(self, base_class):
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
                    if hasattr(module, "is_valid") and not module.is_valid():
                        continue
                    registry[plugin.__name__] = plugin
                if ispkg:
                    _recurse_pkg(module, base_class)

        for pkg in self.plugin_pkg:
            _recurse_pkg(pkg, base_class)
        return registry
