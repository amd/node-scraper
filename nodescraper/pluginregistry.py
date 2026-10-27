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
import ast
import functools
import importlib
import importlib.metadata
import inspect
import logging
import os
import pkgutil
import threading
import types
from collections.abc import MutableMapping
from typing import Callable, Iterable, Iterator, Optional

# Python 3.9 compatibility: EntryPoints type was added in 3.10
try:
    from importlib.metadata import EntryPoints  # type: ignore[attr-defined]
except ImportError:
    EntryPoints = Iterable  # type: ignore[misc, assignment]

import nodescraper.connection as internal_connections
import nodescraper.plugins as internal_plugins
import nodescraper.resultcollators as internal_collators
from nodescraper.interfaces import (
    ConnectionManager,
    PluginInterface,
    PluginResultCollator,
)

# Entry point group names
ENTRY_POINT_PLUGINS = "nodescraper.plugins"
ENTRY_POINT_CONNECTION_MANAGERS = "nodescraper.connection_managers"

# Environment variable enabling lazy plugin loading when ``lazy_load`` is not given explicitly
LAZY_LOAD_ENV_VAR = "NODESCRAPER_LAZY_LOAD"

_logger = logging.getLogger(__name__)


def lazy_load_from_env() -> bool:
    """Return True if ``NODESCRAPER_LAZY_LOAD`` is set to a truthy value (1/true/yes/on)."""
    return os.environ.get(LAZY_LOAD_ENV_VAR, "").strip().lower() in ("1", "true", "yes", "on")


class LazyPluginMapping(MutableMapping):
    """Mapping of plugin name to plugin class that imports each class on first access.

    Listing names (``keys()``, ``in``, ``len``, iteration) never imports plugin modules.
    ``mapping[name]`` / ``get(name)`` import just that plugin. A plugin that fails to
    import or is not valid is logged and treated as missing; other plugins are unaffected.
    ``items()`` / ``values()`` / ``copy()`` resolve every plugin.
    """

    def __init__(self, base_class: type) -> None:
        self._base_class = base_class
        self._loaders: dict[str, Callable[[], Optional[type]]] = {}
        self._resolved: dict[str, type] = {}
        self._failed: set[str] = set()
        self._lock = threading.RLock()

    def add_loader(self, name: str, loader: Callable[[], Optional[type]]) -> None:
        """Register a callable that returns the class for ``name`` when first needed."""
        with self._lock:
            self._loaders[name] = loader
            self._resolved.pop(name, None)
            self._failed.discard(name)

    def is_resolved(self, name: str) -> bool:
        return name in self._resolved

    def __getitem__(self, name: str) -> type:
        resolved = self._resolved.get(name)
        if resolved is not None:
            return resolved
        with self._lock:
            if name in self._resolved:
                return self._resolved[name]
            loader = self._loaders.get(name)
            if loader is None or name in self._failed:
                raise KeyError(name)
            try:
                cls = loader()
            except Exception as exc:  # a broken plugin must not break the others
                _logger.warning("Unable to load plugin %s: %s", name, exc)
                self._failed.add(name)
                raise KeyError(name) from exc
            if cls is None or not PluginRegistry._valid_sub_class_check(cls, self._base_class):
                self._failed.add(name)
                raise KeyError(name)
            if hasattr(cls, "is_valid") and not cls.is_valid():
                self._failed.add(name)
                raise KeyError(name)
            self._resolved[name] = cls
            return cls

    def __setitem__(self, name: str, value: type) -> None:
        with self._lock:
            self._resolved[name] = value
            self._loaders[name] = lambda: value
            self._failed.discard(name)

    def __delitem__(self, name: str) -> None:
        with self._lock:
            if name not in self._loaders:
                raise KeyError(name)
            del self._loaders[name]
            self._resolved.pop(name, None)
            self._failed.discard(name)

    def __contains__(self, name: object) -> bool:
        return name in self._loaders and name not in self._failed

    def __iter__(self) -> Iterator[str]:
        return iter([n for n in list(self._loaders) if n not in self._failed])

    def __len__(self) -> int:
        return len(self._loaders) - len(self._failed)

    def items(self):  # type: ignore[override]
        """Resolve all plugins and return ``(name, class)`` pairs, skipping unloadable ones."""
        pairs = [(n, self._try_get(n)) for n in list(self)]
        return [(n, cls) for n, cls in pairs if cls is not None]

    def values(self):  # type: ignore[override]
        return [cls for _, cls in self.items()]

    def copy(self) -> dict[str, type]:
        """Return a plain dict of all loadable plugins (resolves every plugin)."""
        return dict(self.items())

    def _try_get(self, name: str) -> Optional[type]:
        try:
            return self[name]
        except KeyError:
            return None


class PluginRegistry:
    """This class dynamically loads plugins. Internal plugins are loaded by default using
    the ``nodescraper.plugins``, ``nodescraper.connection``, and ``nodescraper.resultcollators`` packages.
    A caller of node-scraper can also specify entry points for plugins and connection managers. The
    user could also define entrypoints which ``nodescraper.connection_managers`` or ``nodescraper.plugins``
    entry point groups. The PluginRegistry will load these plugins and connection managers as well.
    """

    # Class-level caches for entry points (shared across all instances)
    _entry_point_plugins_cache: Optional[dict[str, type]] = None
    _entry_point_connection_managers_cache: Optional[dict[str, type]] = None
    # Cache for loaded modules to avoid re-importing
    _module_cache: dict[str, types.ModuleType] = {}
    # Cache for entry points by group name
    _entry_points_cache: dict[str, EntryPoints] = {}
    # Cache for the lazy-mode plugin name index (name -> (module, class))
    _plugin_index_cache: Optional[dict[str, tuple[str, str]]] = None

    # Global cache control switch
    _use_cache: bool = True

    # Single lock for all cache operations to ensure atomicity
    _cache_lock = threading.RLock()

    def __init__(
        self,
        plugin_pkg: Optional[list[types.ModuleType]] = None,
        load_internal_plugins: bool = True,
        load_entry_point_plugins: bool = True,
        load_entry_point_connection_managers: bool = True,
        lazy_load: Optional[bool] = None,
    ) -> None:
        """Initialize the PluginRegistry with optional plugin packages.

        Args:
            plugin_pkg (Optional[list[types.ModuleType]], optional): The module to search for plugins in. Defaults to None.
            load_internal_plugins (bool, optional): Whether internal plugin should be loaded. Defaults to True.
            load_entry_point_plugins (bool, optional): Whether to load plugins from entry points. Defaults to True.
            load_entry_point_connection_managers (bool, optional): Whether to load connection managers from the
                ``nodescraper.connection_managers`` entry-point group. Defaults to True.
            lazy_load (Optional[bool], optional): If True, ``plugins`` is a :class:`LazyPluginMapping` and plugin
                modules are imported only when a plugin is first accessed. If None, the
                ``NODESCRAPER_LAZY_LOAD`` environment variable decides (default: eager).
        """
        self.lazy: bool = lazy_load_from_env() if lazy_load is None else lazy_load

        if load_internal_plugins:
            self.plugin_pkg = [
                internal_plugins,
                internal_connections,
                internal_collators,
            ]
        else:
            self.plugin_pkg = []

        if plugin_pkg:
            self.plugin_pkg += plugin_pkg

        self.plugins: MutableMapping[str, type[PluginInterface]]
        if self.lazy:
            self._init_lazy(plugin_pkg or [], load_internal_plugins)
        else:
            self.plugins = PluginRegistry.load_plugins(PluginInterface, self.plugin_pkg)
            self.connection_managers: dict[str, type[ConnectionManager]] = (
                PluginRegistry.load_plugins(ConnectionManager, self.plugin_pkg)
            )
            self.result_collators: dict[str, type[PluginResultCollator]] = (
                PluginRegistry.load_plugins(PluginResultCollator, self.plugin_pkg)
            )

        if load_entry_point_connection_managers:
            for (
                name,
                mgr_cls,
            ) in PluginRegistry.load_connection_managers_from_entry_points().items():
                self.connection_managers[name] = mgr_cls

        if load_entry_point_plugins:
            if self.lazy:
                self._add_lazy_entry_point_plugins()
            else:
                self.plugins.update(self.load_plugins_from_entry_points())

    def _init_lazy(self, extra_pkgs: list[types.ModuleType], load_internal: bool) -> None:
        """Lazy setup: index internal plugin names without importing them.

        Connection managers and result collators are few, so they are still loaded eagerly,
        but only from their own packages (not by walking every plugin module).
        """
        lazy_plugins = LazyPluginMapping(PluginInterface)
        if load_internal:
            index = PluginRegistry._internal_plugin_index()
            for name, (module_name, class_name) in index.items():
                lazy_plugins.add_loader(
                    name,
                    functools.partial(PluginRegistry._import_class, module_name, class_name),
                )
        if extra_pkgs:
            # Caller-supplied packages have no naming convention to index; load them directly
            for name, cls in PluginRegistry.load_plugins(PluginInterface, extra_pkgs).items():
                lazy_plugins[name] = cls
        self.plugins = lazy_plugins

        non_plugin_pkgs = ([internal_connections] if load_internal else []) + extra_pkgs
        self.connection_managers = PluginRegistry.load_plugins(ConnectionManager, non_plugin_pkgs)
        collator_pkgs = ([internal_collators] if load_internal else []) + extra_pkgs
        self.result_collators = PluginRegistry.load_plugins(PluginResultCollator, collator_pkgs)

    def _add_lazy_entry_point_plugins(self) -> None:
        """Register entry-point plugins by entry-point name; ``load()`` runs on first access."""
        assert isinstance(self.plugins, LazyPluginMapping)
        for entry_point in PluginRegistry.load_entry_points(ENTRY_POINT_PLUGINS):
            # Eager mode keys by class __name__, which is the attribute in ``module:Class``.
            value = getattr(entry_point, "value", "") or ""
            attr = value.partition(":")[2].strip().split(".")[-1].split("[")[0].strip()
            self.plugins.add_loader(
                attr or entry_point.name,
                entry_point.load,  # type: ignore[attr-defined]
            )

    @staticmethod
    def _import_class(module_name: str, class_name: str) -> type:
        """Import ``module_name`` (through the shared module cache) and return ``class_name``."""
        with PluginRegistry._cache_lock:
            module = PluginRegistry._module_cache.get(module_name)
        if module is None:
            module = importlib.import_module(module_name)
            if PluginRegistry._use_cache:
                with PluginRegistry._cache_lock:
                    PluginRegistry._module_cache[module_name] = module
        return getattr(module, class_name)

    @staticmethod
    def _base_name(node: ast.expr) -> str:
        if isinstance(node, ast.Subscript):
            node = node.value
        if isinstance(node, ast.Attribute):
            return node.attr
        if isinstance(node, ast.Name):
            return node.id
        return ""

    @staticmethod
    def _scan_plugin_index(pkg: types.ModuleType) -> dict[str, tuple[str, str]]:
        """Map plugin class name to ``(module, class)`` by parsing ``*plugin*.py`` sources.

        Nothing is imported. A class is a candidate if a base class name contains ``Plugin``;
        validity is checked when the class is resolved.
        """
        index: dict[str, tuple[str, str]] = {}
        for root in list(getattr(pkg, "__path__", [])):
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
                for filename in sorted(filenames):
                    if "plugin" not in filename or not filename.endswith(".py"):
                        continue
                    path = os.path.join(dirpath, filename)
                    rel = os.path.relpath(path, root)[: -len(".py")]
                    module_name = ".".join([pkg.__name__, *rel.split(os.sep)])
                    try:
                        with open(path, "r", encoding="utf-8") as src:
                            tree = ast.parse(src.read(), filename=path)
                    except (OSError, SyntaxError, ValueError) as exc:
                        _logger.warning("Unable to index plugin module %s: %s", path, exc)
                        continue
                    for node in tree.body:
                        if not isinstance(node, ast.ClassDef):
                            continue
                        bases = [PluginRegistry._base_name(b) for b in node.bases]
                        if any("Plugin" in b for b in bases):
                            index[node.name] = (module_name, node.name)
        return index

    @staticmethod
    def _internal_plugin_index() -> dict[str, tuple[str, str]]:
        """Cached name index for ``nodescraper.plugins``."""
        with PluginRegistry._cache_lock:
            if PluginRegistry._plugin_index_cache is None or not PluginRegistry._use_cache:
                PluginRegistry._plugin_index_cache = PluginRegistry._scan_plugin_index(
                    internal_plugins
                )
            return PluginRegistry._plugin_index_cache

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
                # Check module cache first with thread safety (if caching enabled)
                if PluginRegistry._use_cache:
                    with PluginRegistry._cache_lock:
                        if module_name in PluginRegistry._module_cache:
                            module = PluginRegistry._module_cache[module_name]
                        else:
                            module = importlib.import_module(module_name)
                            PluginRegistry._module_cache[module_name] = module
                else:
                    module = importlib.import_module(module_name)

                for _, plugin in inspect.getmembers(
                    module,
                    lambda x: PluginRegistry._valid_sub_class_check(
                        in_cls=x, base_class=base_class
                    ),
                ):
                    if hasattr(plugin, "is_valid") and not plugin.is_valid():
                        continue
                    registry[plugin.__name__] = plugin
                if ispkg:
                    _recurse_pkg(module, base_class)

        for pkg in search_modules:
            _recurse_pkg(pkg, base_class)
        return registry

    @staticmethod
    def _valid_sub_class_check(in_cls: type, base_class: type) -> bool:
        """Check if a class is a subclass of the specified base class.

        Args:
            cls (type): The class to check.
            base_class (type): The base class to check against.

        Returns:
            bool: True if cls is a subclass of base_class, False otherwise.
        """
        if not inspect.isclass(in_cls):
            return False
        try:
            return issubclass(in_cls, base_class) and not inspect.isabstract(in_cls)
        except TypeError:
            return False

    @staticmethod
    def _load_connection_managers_uncached() -> dict[str, type]:
        """Internal: Load connection managers without caching logic."""
        managers: dict[str, type] = {}
        eps: Iterable = PluginRegistry.load_entry_points(ENTRY_POINT_CONNECTION_MANAGERS)

        for entry_point in eps:
            loaded = entry_point.load()  # type: ignore[attr-defined, union-attr]
            if not PluginRegistry._valid_sub_class_check(
                in_cls=loaded, base_class=ConnectionManager
            ):
                continue
            if hasattr(loaded, "is_valid") and not loaded.is_valid():
                continue
            cls = loaded
            managers[cls.__name__] = cls
            ep_name = getattr(entry_point, "name", None)
            if ep_name and ep_name != cls.__name__:
                managers[ep_name] = cls
        return managers.copy()

    @staticmethod
    def load_connection_managers_from_entry_points() -> dict[str, type]:
        """Load ConnectionManager subclasses from ``nodescraper.connection_managers`` entry points.

        The class ``__name__`` is always a lookup key. If the distribution entry-point name
        differs, it is registered as an alias (for ``--connection-config`` JSON keys).

        Returns:
            dict[str, type]: Map of lookup key to connection manager class.
        """
        # Return cached result if caching is enabled and cache exists
        if (
            PluginRegistry._use_cache
            and PluginRegistry._entry_point_connection_managers_cache is not None
        ):
            return PluginRegistry._entry_point_connection_managers_cache.copy()

        # If caching disabled, skip lock and always reload
        if not PluginRegistry._use_cache:
            return PluginRegistry._load_connection_managers_uncached().copy()

        with PluginRegistry._cache_lock:
            # Check again inside the lock to prevent duplicate work
            if PluginRegistry._entry_point_connection_managers_cache is not None:
                return PluginRegistry._entry_point_connection_managers_cache.copy()

            managers = PluginRegistry._load_connection_managers_uncached()

            # Cache the result
            PluginRegistry._entry_point_connection_managers_cache = managers
            return managers.copy()

    @staticmethod
    def _load_entry_points_uncached(entry_point: str) -> EntryPoints:
        """Internal: Load entry points without caching logic."""
        try:
            eps: EntryPoints = importlib.metadata.entry_points(group=entry_point)  # type: ignore[call-arg]
        except TypeError:
            all_eps: EntryPoints = importlib.metadata.entry_points()  # type: ignore[assignment]
            eps = all_eps.get(entry_point, [])  # type: ignore[assignment, attr-defined, arg-type]
        return eps

    @staticmethod
    def load_entry_points(entry_point: str) -> EntryPoints:
        # Return cached result if caching is enabled and cache exists
        if PluginRegistry._use_cache and entry_point in PluginRegistry._entry_points_cache:
            return PluginRegistry._entry_points_cache[entry_point]

        # If caching disabled, skip lock and always reload
        if not PluginRegistry._use_cache:
            return PluginRegistry._load_entry_points_uncached(entry_point)

        with PluginRegistry._cache_lock:
            # Check again inside the lock to prevent duplicate work
            if entry_point in PluginRegistry._entry_points_cache:
                return PluginRegistry._entry_points_cache[entry_point]

            eps = PluginRegistry._load_entry_points_uncached(entry_point)

            # Cache the result
            PluginRegistry._entry_points_cache[entry_point] = eps
            return eps

    @staticmethod
    def _load_plugins_uncached() -> dict[str, type]:
        """Internal: Load plugins without caching logic."""
        plugins = {}
        eps: Iterable = PluginRegistry.load_entry_points(ENTRY_POINT_PLUGINS)
        for entry_point in eps:
            plugin_class = entry_point.load()  # type: ignore[attr-defined, union-attr]
            if not PluginRegistry._valid_sub_class_check(
                in_cls=plugin_class, base_class=PluginInterface
            ):
                continue
            if hasattr(plugin_class, "is_valid") and not plugin_class.is_valid():
                continue

            plugins[plugin_class.__name__] = plugin_class
        return plugins

    @staticmethod
    def load_plugins_from_entry_points() -> dict[str, type]:
        """Load plugins registered via entry points.

        Returns:
            dict[str, type]: A dictionary mapping plugin names to their classes.
        """
        # Return cached result if caching is enabled and cache exists
        if PluginRegistry._use_cache and PluginRegistry._entry_point_plugins_cache is not None:
            return PluginRegistry._entry_point_plugins_cache.copy()

        # If caching disabled, skip lock and always reload
        if not PluginRegistry._use_cache:
            return PluginRegistry._load_plugins_uncached()

        with PluginRegistry._cache_lock:
            # Check again inside the lock to prevent duplicate work
            if PluginRegistry._entry_point_plugins_cache is not None:
                return PluginRegistry._entry_point_plugins_cache.copy()

            plugins = PluginRegistry._load_plugins_uncached()

            # Cache the result - no need to copy before caching
            PluginRegistry._entry_point_plugins_cache = plugins
            return plugins.copy()

    @classmethod
    def clear_caches(cls) -> None:
        """Clear all caches. Useful for testing or when plugins are dynamically installed.

        Thread-safe: Acquires all locks to ensure no other thread is accessing caches.
        """
        global _default_registry
        with cls._cache_lock:
            cls._entry_point_plugins_cache = None
            cls._entry_point_connection_managers_cache = None
            cls._plugin_index_cache = None
            cls._module_cache.clear()
            cls._entry_points_cache.clear()
            _default_registry = None


_default_registry: Optional[PluginRegistry] = None


def default_registry() -> PluginRegistry:
    """Return the process-wide shared registry, creating it on first use.

    The CLI installs its own registry with :func:`set_default_registry`; embedders and
    library code that are not handed a registry share this one instead of building new ones.
    """
    global _default_registry
    with PluginRegistry._cache_lock:
        existing = _default_registry
    if existing is not None:
        return existing
    created = PluginRegistry()
    with PluginRegistry._cache_lock:
        if _default_registry is None:
            _default_registry = created
        return _default_registry


def set_default_registry(registry: Optional[PluginRegistry]) -> None:
    """Install ``registry`` as the shared default (``None`` resets it)."""
    global _default_registry
    with PluginRegistry._cache_lock:
        _default_registry = registry
