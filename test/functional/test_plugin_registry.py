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
"""Functional tests for plugin registry and plugin loading."""

import inspect
import threading

from nodescraper.pluginregistry import PluginRegistry


def test_plugin_registry_loads_plugins():
    """Test that PluginRegistry successfully loads built-in plugins."""
    registry = PluginRegistry()

    assert len(registry.plugins) > 0
    plugin_names = [name.lower() for name in registry.plugins.keys()]
    expected_plugins = ["biosplugin", "kernelplugin", "osplugin"]

    for expected in expected_plugins:
        assert expected in plugin_names


def test_plugin_registry_has_connection_managers():
    """Test that PluginRegistry loads connection managers."""
    registry = PluginRegistry()

    assert len(registry.connection_managers) > 0
    conn_names = [name.lower() for name in registry.connection_managers.keys()]
    assert "inbandconnectionmanager" in conn_names


def test_plugin_registry_list_plugins():
    """Test that PluginRegistry stores plugins in a dictionary."""
    registry = PluginRegistry()
    plugin_dict = registry.plugins

    assert isinstance(plugin_dict, dict)
    assert len(plugin_dict) > 0
    assert all(isinstance(name, str) for name in plugin_dict.keys())
    assert all(inspect.isclass(cls) for cls in plugin_dict.values())


def test_plugin_registry_get_plugin():
    """Test that PluginRegistry can retrieve a specific plugin."""
    registry = PluginRegistry()
    plugin_names = list(registry.plugins.keys())
    assert len(plugin_names) > 0

    first_plugin_name = plugin_names[0]
    plugin = registry.plugins[first_plugin_name]

    assert plugin is not None
    assert hasattr(plugin, "run")


# ============================================================================
# CACHING TESTS
# ============================================================================


def test_entry_point_plugins_are_cached():
    """Test that entry point plugins are cached and subsequent calls use the cache."""
    # Clear cache to start fresh
    PluginRegistry.clear_caches()
    assert PluginRegistry._entry_point_plugins_cache is None

    # First call - should populate cache
    plugins1 = PluginRegistry.load_plugins_from_entry_points()
    assert PluginRegistry._entry_point_plugins_cache is not None

    # Second call - should return from cache (but as a copy)
    plugins2 = PluginRegistry.load_plugins_from_entry_points()

    # Verify it's a copy (different object but same content)
    assert plugins1 is not plugins2, "Should return copy, not same reference"
    assert plugins1 == plugins2, "Content should be identical"


def test_cache_returns_copy_prevents_corruption():
    """Test that cache returns a copy to prevent caller modifications from corrupting cache."""
    PluginRegistry.clear_caches()

    # Get plugins from cache
    plugins1 = PluginRegistry.load_plugins_from_entry_points()
    plugins2 = PluginRegistry.load_plugins_from_entry_points()

    # Modify first copy
    if plugins1:
        test_key = list(plugins1.keys())[0]
        plugins1.pop(test_key)
        assert test_key not in plugins1

    # Second copy should be unaffected
    if plugins2:
        test_key = list(plugins2.keys())[0]
        assert test_key in plugins2, "Cache was corrupted by caller modification"


def test_concurrent_cache_access_thread_safe():
    """Test that concurrent cache access is thread-safe with no race conditions."""
    PluginRegistry.clear_caches()
    results = []
    errors = []

    def load_plugins_worker():
        try:
            plugins = PluginRegistry.load_plugins_from_entry_points()
            results.append(plugins)
        except Exception as e:
            errors.append(e)

    # Create 10 threads that simultaneously try to load plugins
    threads = [threading.Thread(target=load_plugins_worker) for _ in range(10)]

    # Start all threads at once
    for thread in threads:
        thread.start()

    # Wait for completion
    for thread in threads:
        thread.join()

    # No errors should occur
    assert len(errors) == 0, f"Thread safety errors: {errors}"

    # All threads should get consistent results
    assert len(results) == 10
    first_keys = set(results[0].keys())
    for result in results[1:]:
        assert set(result.keys()) == first_keys, "Inconsistent results across threads"


def test_clear_caches_resets_all_caches():
    """Test that clear_caches properly clears all cache storage."""
    # Populate all caches
    PluginRegistry.load_plugins_from_entry_points()
    PluginRegistry.load_connection_managers_from_entry_points()
    PluginRegistry.load_entry_points("nodescraper.plugins")

    # Verify caches are populated
    assert PluginRegistry._entry_point_plugins_cache is not None
    assert PluginRegistry._entry_point_connection_managers_cache is not None
    assert len(PluginRegistry._entry_points_cache) > 0

    # Clear all caches
    PluginRegistry.clear_caches()

    # Verify all caches are cleared
    assert PluginRegistry._entry_point_plugins_cache is None
    assert PluginRegistry._entry_point_connection_managers_cache is None
    assert len(PluginRegistry._entry_points_cache) == 0
    assert len(PluginRegistry._module_cache) == 0
