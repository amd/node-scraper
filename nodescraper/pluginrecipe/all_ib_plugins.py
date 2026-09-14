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
from __future__ import annotations

from nodescraper.connection.inband import InBandConnectionManager

from .discovery import PluginDiscovery
from .pluginrecipe import PluginRecipe


class AllIbPlugins(PluginRecipe):
    """Run all registered in-band plugins with default arguments."""

    @classmethod
    def plugin_names(cls) -> tuple[str, ...]:
        """Return every in-band plugin registered at runtime.

        Returns:
            tuple[str, ...]: Sorted names of all in-band plugins in the plugin registry.
        """
        discovery = PluginDiscovery()
        return tuple(
            sorted(
                name
                for name in discovery.registered_plugin_names()
                if getattr(discovery.load_plugin_class(name), "CONNECTION_TYPE", None)
                is InBandConnectionManager
            )
        )
