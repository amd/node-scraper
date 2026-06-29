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
"""Functional tests for plugin discovery functionality."""

import threading

from nodescraper.pluginrecipe.discovery import PluginDiscovery
from nodescraper.pluginregistry import PluginRegistry


def test_plugin_discovery_initialization():
    """Test that PluginDiscovery can be initialized with and without cache."""
    # With cache (default)
    discovery_cached = PluginDiscovery()
    assert discovery_cached._use_cache is True

    # Without cache
    discovery_no_cache = PluginDiscovery(use_cache=False)
    assert discovery_no_cache._use_cache is False


def test_registered_plugin_names():
    """Test that registered_plugin_names returns plugin names."""
    discovery = PluginDiscovery()
    plugin_names = discovery.registered_plugin_names()

    assert isinstance(plugin_names, tuple)
    assert len(plugin_names) > 0
    # Should be sorted
    assert plugin_names == tuple(sorted(plugin_names))
    # All should be strings
    assert all(isinstance(name, str) for name in plugin_names)


def test_registered_plugin_names_matches_registry():
    """Test that registered_plugin_names matches the PluginRegistry."""
    discovery = PluginDiscovery()
    registry = PluginRegistry()

    discovery_names = set(discovery.registered_plugin_names())
    registry_names = set(registry.plugins.keys())

    assert discovery_names == registry_names


def test_load_plugin_class_existing():
    """Test loading an existing plugin class."""
    discovery = PluginDiscovery()
    plugin_names = discovery.registered_plugin_names()

    if len(plugin_names) == 0:
        return  # Skip if no plugins

    # Load first plugin
    plugin_name = plugin_names[0]
    plugin_class = discovery.load_plugin_class(plugin_name)

    assert plugin_class is not None
    assert hasattr(plugin_class, "run")


def test_load_plugin_class_nonexistent():
    """Test loading a non-existent plugin returns None."""
    discovery = PluginDiscovery()
    plugin_class = discovery.load_plugin_class("NonExistentPlugin12345")

    assert plugin_class is None


def test_plugin_has_collector():
    """Test checking if plugins have COLLECTOR attribute."""
    discovery = PluginDiscovery()
    plugin_names = discovery.registered_plugin_names()

    # Test with all plugins
    for plugin_name in plugin_names:
        has_collector = discovery.plugin_has_collector(plugin_name)
        assert isinstance(has_collector, bool)

        # Verify against actual plugin class
        plugin_class = discovery.load_plugin_class(plugin_name)
        expected = getattr(plugin_class, "COLLECTOR", None) is not None
        assert has_collector == expected


def test_plugin_has_collector_nonexistent():
    """Test that non-existent plugins return False for has_collector."""
    discovery = PluginDiscovery()
    assert discovery.plugin_has_collector("NonExistentPlugin12345") is False


def test_plugin_has_analyzer():
    """Test checking if plugins have ANALYZER attribute."""
    discovery = PluginDiscovery()
    plugin_names = discovery.registered_plugin_names()

    # Test with all plugins
    for plugin_name in plugin_names:
        has_analyzer = discovery.plugin_has_analyzer(plugin_name)
        assert isinstance(has_analyzer, bool)

        # Verify against actual plugin class
        plugin_class = discovery.load_plugin_class(plugin_name)
        expected = getattr(plugin_class, "ANALYZER", None) is not None
        assert has_analyzer == expected


def test_plugin_has_analyzer_nonexistent():
    """Test that non-existent plugins return False for has_analyzer."""
    discovery = PluginDiscovery()
    assert discovery.plugin_has_analyzer("NonExistentPlugin12345") is False


def test_plugins_with_collector():
    """Test filtering plugins that have COLLECTOR attribute."""
    discovery = PluginDiscovery()
    all_plugins = discovery.registered_plugin_names()

    plugins_with_collector = discovery.plugins_with_collector(all_plugins)

    assert isinstance(plugins_with_collector, tuple)
    # Should be sorted
    assert plugins_with_collector == tuple(sorted(plugins_with_collector))

    # Verify each one actually has COLLECTOR
    for plugin_name in plugins_with_collector:
        assert discovery.plugin_has_collector(plugin_name)


def test_plugins_with_collector_empty():
    """Test plugins_with_collector with empty input."""
    discovery = PluginDiscovery()
    result = discovery.plugins_with_collector([])
    assert result == ()


def test_plugins_with_collector_mixed():
    """Test plugins_with_collector with mix of valid and invalid names."""
    discovery = PluginDiscovery()
    all_plugins = discovery.registered_plugin_names()

    if len(all_plugins) == 0:
        return

    # Mix real and fake plugin names
    test_names = list(all_plugins[:3]) + ["FakePlugin1", "FakePlugin2"]
    result = discovery.plugins_with_collector(test_names)

    # Should only contain valid plugins with collector
    for name in result:
        assert name in all_plugins
        assert discovery.plugin_has_collector(name)


def test_plugins_with_analyzer():
    """Test filtering plugins that have ANALYZER attribute."""
    discovery = PluginDiscovery()
    all_plugins = discovery.registered_plugin_names()

    plugins_with_analyzer = discovery.plugins_with_analyzer(all_plugins)

    assert isinstance(plugins_with_analyzer, tuple)
    # Should be sorted
    assert plugins_with_analyzer == tuple(sorted(plugins_with_analyzer))

    # Verify each one actually has ANALYZER
    for plugin_name in plugins_with_analyzer:
        assert discovery.plugin_has_analyzer(plugin_name)


def test_plugins_with_analyzer_empty():
    """Test plugins_with_analyzer with empty input."""
    discovery = PluginDiscovery()
    result = discovery.plugins_with_analyzer([])
    assert result == ()


def test_plugins_with_analyzer_mixed():
    """Test plugins_with_analyzer with mix of valid and invalid names."""
    discovery = PluginDiscovery()
    all_plugins = discovery.registered_plugin_names()

    if len(all_plugins) == 0:
        return

    # Mix real and fake plugin names
    test_names = list(all_plugins[:3]) + ["FakePlugin1", "FakePlugin2"]
    result = discovery.plugins_with_analyzer(test_names)

    # Should only contain valid plugins with analyzer
    for name in result:
        assert name in all_plugins
        assert discovery.plugin_has_analyzer(name)


def test_plugin_names_matching():
    """Test plugin_names_matching returns only registered plugins."""
    discovery = PluginDiscovery()
    all_plugins = discovery.registered_plugin_names()

    if len(all_plugins) == 0:
        return

    # Test with mix of valid and invalid names
    test_names = [
        all_plugins[0] if len(all_plugins) > 0 else "ValidPlugin",
        "NonExistentPlugin1",
        all_plugins[1] if len(all_plugins) > 1 else "AnotherPlugin",
        "NonExistentPlugin2",
    ]

    matched = discovery.plugin_names_matching(test_names)

    assert isinstance(matched, tuple)
    # Should be sorted
    assert matched == tuple(sorted(matched))
    # Should only contain plugins that exist
    for name in matched:
        assert name in all_plugins


def test_plugin_names_matching_empty():
    """Test plugin_names_matching with empty input."""
    discovery = PluginDiscovery()
    matched = discovery.plugin_names_matching([])
    assert matched == ()


def test_plugin_names_matching_all_invalid():
    """Test plugin_names_matching with all non-existent plugins."""
    discovery = PluginDiscovery()
    matched = discovery.plugin_names_matching(["Fake1", "Fake2", "NotReal"])
    assert matched == ()


def test_plugin_names_matching_all_valid():
    """Test plugin_names_matching with all valid plugins."""
    discovery = PluginDiscovery()
    all_plugins = discovery.registered_plugin_names()

    if len(all_plugins) == 0:
        return

    # Take first 3 plugins
    test_plugins = all_plugins[: min(3, len(all_plugins))]
    matched = discovery.plugin_names_matching(test_plugins)

    # Should return all of them
    assert set(matched) == set(test_plugins)
    # Should be sorted
    assert matched == tuple(sorted(matched))


def test_cache_behavior():
    """Test that caching works correctly."""
    # Clear any existing cache
    PluginDiscovery._plugin_cache = None

    discovery = PluginDiscovery(use_cache=True)

    # First call should populate class-level cache
    assert PluginDiscovery._plugin_cache is None
    plugins1 = discovery.registered_plugin_names()
    assert PluginDiscovery._plugin_cache is not None

    # Second call should use cache and return same results
    plugins2 = discovery.registered_plugin_names()
    assert plugins1 == plugins2


def test_no_cache_behavior():
    """Test that use_cache=False bypasses cache."""
    # Clear cache
    PluginDiscovery._plugin_cache = None

    discovery = PluginDiscovery(use_cache=False)

    # Get plugins without caching
    plugins = discovery.registered_plugin_names()
    # Should still get valid results
    assert len(plugins) > 0
    # Cache should remain None
    assert PluginDiscovery._plugin_cache is None


def test_clear_cache():
    """Test that clear_cache properly clears the cache."""
    discovery = PluginDiscovery(use_cache=True)

    # Populate cache by calling registered_plugin_names
    discovery.registered_plugin_names()
    assert PluginDiscovery._plugin_cache is not None

    # Clear cache
    discovery.clear_cache()
    assert PluginDiscovery._plugin_cache is None


def test_concurrent_access_thread_safe():
    """Test that concurrent cache access is thread-safe."""
    # Clear cache before test
    PluginDiscovery._plugin_cache = None

    results = []
    errors = []

    def load_plugins_worker():
        try:
            discovery = PluginDiscovery(use_cache=True)
            plugins = discovery.registered_plugin_names()
            results.append(plugins)
        except Exception as e:
            errors.append(e)

    # Create 10 threads
    threads = [threading.Thread(target=load_plugins_worker) for _ in range(10)]

    # Start all threads
    for thread in threads:
        thread.start()

    # Wait for completion
    for thread in threads:
        thread.join()

    # No errors should occur
    assert len(errors) == 0, f"Thread safety errors: {errors}"

    # All threads should get consistent results
    assert len(results) == 10
    first_result = set(results[0])
    for result in results[1:]:
        assert set(result) == first_result


def test_class_attributes():
    """Test that class attributes have expected values."""
    assert PluginDiscovery.COLLECTOR_ATTRIBUTE == "COLLECTOR"
    assert PluginDiscovery.ANALYZER_ATTRIBUTE == "ANALYZER"


def test_load_plugin_class_with_cache():
    """Test load_plugin_class uses cache when enabled."""
    # Clear cache
    PluginDiscovery._plugin_cache = None

    discovery = PluginDiscovery(use_cache=True)
    plugin_names = discovery.registered_plugin_names()

    if len(plugin_names) == 0:
        return

    plugin_name = plugin_names[0]

    # First load should populate cache
    assert PluginDiscovery._plugin_cache is None or len(PluginDiscovery._plugin_cache) > 0
    plugin1 = discovery.load_plugin_class(plugin_name)
    assert plugin1 is not None
    assert PluginDiscovery._plugin_cache is not None

    # Second load should use cache and return same class
    plugin2 = discovery.load_plugin_class(plugin_name)
    assert plugin1 is plugin2


def test_load_plugin_class_without_cache():
    """Test load_plugin_class bypasses cache when disabled."""
    # Clear cache
    PluginDiscovery._plugin_cache = None

    discovery = PluginDiscovery(use_cache=False)
    plugin_names = discovery.registered_plugin_names()

    if len(plugin_names) == 0:
        return

    plugin_name = plugin_names[0]

    # Load without cache
    plugin = discovery.load_plugin_class(plugin_name)
    assert plugin is not None
    # Cache should remain None
    assert PluginDiscovery._plugin_cache is None
