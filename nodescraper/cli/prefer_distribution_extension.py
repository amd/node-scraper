###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
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
"""CLI extension that merges ``nodescraper.plugins`` entry points with distribution preference."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from nodescraper.cli.extension import CliExtension
from nodescraper.plugin_entrypoints import load_plugin_entry_points

if TYPE_CHECKING:
    from nodescraper.configregistry import ConfigRegistry
    from nodescraper.pluginregistry import PluginRegistry


class PreferDistributionPluginsExtension(CliExtension):
    """Merge entry-point plugins into the registry, preferring named distributions on clashes.

    Use when embedding the CLI next to other distributions that register the same
    ``plugin_class.__name__`` (see :func:`~nodescraper.plugin_entrypoints.load_plugin_entry_points`).
    This mirrors loading with :class:`~nodescraper.pluginregistry.PluginRegistry` and
    *prefer_distribution_names*, but applies after the default registry is built so hosts
    can combine internal plugins with a chosen entry-point merge order.
    """

    def __init__(
        self,
        *,
        prefer_distribution_names: Sequence[str],
        entry_point_group: str = "nodescraper.plugins",
    ) -> None:
        self._prefer_distribution_names = tuple(prefer_distribution_names)
        self._entry_point_group = entry_point_group

    def prepare_registries(
        self,
        plugin_reg: PluginRegistry,
        config_reg: ConfigRegistry,
    ) -> None:
        plugin_reg.plugins.update(
            load_plugin_entry_points(
                group=self._entry_point_group,
                prefer_distribution_names=self._prefer_distribution_names,
            )
        )


__all__ = ["PreferDistributionPluginsExtension"]
