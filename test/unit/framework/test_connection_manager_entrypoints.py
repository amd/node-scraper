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
from unittest.mock import MagicMock, patch

from nodescraper.connection.inband.inbandmanager import InBandConnectionManager
from nodescraper.pluginregistry import PluginRegistry


def _entry_points_side_effect_cm_only(mock_ep, *args, **kwargs):
    group = kwargs.get("group")
    if group == "nodescraper.connection_managers":
        return [mock_ep]
    return []


def test_load_connection_managers_from_entry_points_registers_class_and_alias():
    mock_ep = MagicMock()
    mock_ep.name = "AliasInBand"
    mock_ep.load.return_value = InBandConnectionManager

    with patch("nodescraper.pluginregistry.importlib.metadata.entry_points") as mock_eps:
        mock_eps.side_effect = lambda *a, **k: _entry_points_side_effect_cm_only(mock_ep, *a, **k)
        found = PluginRegistry.load_connection_managers_from_entry_points()

    assert found["InBandConnectionManager"] is InBandConnectionManager
    assert found["AliasInBand"] is InBandConnectionManager


def test_plugin_registry_merges_entry_point_connection_managers():
    mock_ep = MagicMock()
    mock_ep.name = "AliasInBand"
    mock_ep.load.return_value = InBandConnectionManager

    with patch("nodescraper.pluginregistry.importlib.metadata.entry_points") as mock_eps:
        mock_eps.side_effect = lambda *a, **k: _entry_points_side_effect_cm_only(mock_ep, *a, **k)
        reg = PluginRegistry(load_entry_point_connection_managers=True)

    assert reg.connection_managers["InBandConnectionManager"] is InBandConnectionManager
    assert reg.connection_managers["AliasInBand"] is InBandConnectionManager


def test_plugin_registry_can_disable_entry_point_connection_managers():
    reg = PluginRegistry(load_entry_point_connection_managers=False)
    assert "InBandConnectionManager" in reg.connection_managers
