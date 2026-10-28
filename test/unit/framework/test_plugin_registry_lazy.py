###############################################################################
#
# MIT License
#
# Copyright (C) 2026 Advanced Micro Devices, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the  Software, and to permit persons to whom the Software is
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
from unittest.mock import MagicMock, patch

import pytest

import nodescraper.plugins as internal_plugins
from nodescraper.interfaces import PluginInterface
from nodescraper.pluginregistry import LazyPluginMapping, PluginRegistry
from nodescraper.plugins.inband.bios.bios_plugin import BiosPlugin
from nodescraper.plugins.inband.kernel.kernel_plugin import KernelPlugin

BIOS_VALUE = "nodescraper.plugins.inband.bios.bios_plugin:BiosPlugin"
KERNEL_VALUE = "nodescraper.plugins.inband.kernel.kernel_plugin:KernelPlugin"


@pytest.fixture(autouse=True)
def clear_cache():
    PluginRegistry.clear_caches()
    yield
    PluginRegistry.clear_caches()


def _entry_point(name, value, loaded):
    ep = MagicMock()
    ep.name = name
    ep.value = value
    if isinstance(loaded, Exception):
        ep.load.side_effect = loaded
    else:
        ep.load.return_value = loaded
    return ep


def _patch_plugin_entry_points(eps):
    def side_effect(*args, **kwargs):
        return eps if kwargs.get("group") == "nodescraper.plugins" else []

    return patch(
        "nodescraper.pluginregistry.importlib.metadata.entry_points", side_effect=side_effect
    )


def test_lazy_registry_uses_lazy_mapping():
    reg = PluginRegistry(lazy_load=True)
    assert reg.lazy
    assert isinstance(reg.plugins, LazyPluginMapping)


def test_lazy_internal_plugins_match_eager_scan():
    """Every internal plugin must be declared in the ``nodescraper.plugins`` entry points."""
    lazy = PluginRegistry(
        lazy_load=True, load_entry_point_plugins=False, load_entry_point_connection_managers=False
    )
    eager = PluginRegistry.load_plugins(PluginInterface, [internal_plugins])
    assert sorted(lazy.plugins) == sorted(eager)
    for name, cls in eager.items():
        assert lazy.plugins[name] is cls


def test_lazy_entry_points_not_loaded_until_accessed():
    bios_ep = _entry_point("BiosPlugin", BIOS_VALUE, BiosPlugin)
    kernel_ep = _entry_point("KernelPlugin", KERNEL_VALUE, KernelPlugin)
    with _patch_plugin_entry_points([bios_ep, kernel_ep]):
        reg = PluginRegistry(
            lazy_load=True,
            load_entry_point_connection_managers=False,
        )
        assert sorted(reg.plugins) == ["BiosPlugin", "KernelPlugin"]
        bios_ep.load.assert_not_called()
        kernel_ep.load.assert_not_called()

        assert reg.plugins["BiosPlugin"] is BiosPlugin
        bios_ep.load.assert_called_once()
        kernel_ep.load.assert_not_called()
        assert reg.plugins.is_resolved("BiosPlugin")
        assert not reg.plugins.is_resolved("KernelPlugin")

        assert reg.plugins["BiosPlugin"] is BiosPlugin
        bios_ep.load.assert_called_once()


def test_lazy_internal_only_skips_external_entry_points():
    bios_ep = _entry_point("BiosPlugin", BIOS_VALUE, BiosPlugin)
    external_ep = _entry_point("ExtPlugin", "ext_pkg.ext_plugin:ExtPlugin", KernelPlugin)
    with _patch_plugin_entry_points([bios_ep, external_ep]):
        reg = PluginRegistry(
            lazy_load=True,
            load_entry_point_plugins=False,
            load_entry_point_connection_managers=False,
        )
        assert list(reg.plugins) == ["BiosPlugin"]
        external_ep.load.assert_not_called()


def test_lazy_external_entry_point_keyed_by_class_name():
    external_ep = _entry_point("alias", "ext_pkg.ext_plugin:KernelPlugin", KernelPlugin)
    with _patch_plugin_entry_points([external_ep]):
        reg = PluginRegistry(
            lazy_load=True,
            load_internal_plugins=False,
            load_entry_point_connection_managers=False,
        )
        assert list(reg.plugins) == ["KernelPlugin"]
        assert reg.plugins["KernelPlugin"] is KernelPlugin


def test_lazy_broken_entry_point_does_not_affect_others():
    broken_ep = _entry_point(
        "BrokenPlugin", "nodescraper.plugins.nope:BrokenPlugin", ImportError("boom")
    )
    bios_ep = _entry_point("BiosPlugin", BIOS_VALUE, BiosPlugin)
    with _patch_plugin_entry_points([broken_ep, bios_ep]):
        reg = PluginRegistry(lazy_load=True, load_entry_point_connection_managers=False)
        assert "BrokenPlugin" not in reg.plugins
        assert "BrokenPlugin" not in list(reg.plugins)
        assert reg.plugins["BiosPlugin"] is BiosPlugin
        with pytest.raises(KeyError):
            reg.plugins["BrokenPlugin"]


def test_lazy_non_plugin_entry_point_is_treated_as_missing():
    bad_ep = _entry_point("NotAPlugin", "nodescraper.plugins.x:NotAPlugin", dict)
    with _patch_plugin_entry_points([bad_ep]):
        reg = PluginRegistry(
            lazy_load=True,
            load_internal_plugins=False,
            load_entry_point_connection_managers=False,
        )
        assert "NotAPlugin" not in reg.plugins
        assert len(reg.plugins) == 0


def test_lazy_load_env_var(monkeypatch):
    monkeypatch.setenv("NODESCRAPER_LAZY_LOAD", "1")
    assert PluginRegistry(load_entry_point_plugins=False).lazy
    monkeypatch.setenv("NODESCRAPER_LAZY_LOAD", "0")
    assert not PluginRegistry(load_entry_point_plugins=False).lazy
