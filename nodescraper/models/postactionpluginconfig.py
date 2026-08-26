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
from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from nodescraper.models.postactioncondition import PostActionCondition

if TYPE_CHECKING:
    from nodescraper.models.pluginresult import PluginResult


class PostActionPluginConfig(BaseModel):
    """Configuration for a single post-action plugin.

    A post-action plugin runs after all primary plugins have completed, but only
    if at least one condition in ``conditions`` is satisfied by the primary results
    (OR semantics across conditions).

    The ``plugin`` and ``plugin_args`` fields mirror the structure of a regular
    entry in :attr:`~nodescraper.models.PluginConfig.plugins` — the plugin is
    looked up by name in the registry and run identically to a primary plugin.

    Example JSON config entry::

        {
          "plugin": "SomeRemediationPlugin",
          "plugin_args": {"collection": true, "analysis": false},
          "conditions": [
            {"plugin": "DmesgPlugin", "status": "ERROR"},
            {"event_priority": "CRITICAL", "event_description_contains": "GPU reset"}
          ]
        }
    """

    plugin: str
    """Name of the plugin to run — must be registered in the plugin registry."""

    plugin_args: dict = Field(default_factory=dict)
    """Arguments forwarded verbatim to ``plugin.run()``.  Same shape as entries
    in :attr:`~nodescraper.models.PluginConfig.plugins`, e.g.::

        {
          "collection": True,
          "analysis": False,
          "collection_args": {"some_arg": "value"}
        }
    """

    conditions: list[PostActionCondition] = Field(default_factory=list)
    """List of conditions (OR'd).  If any one condition is met by the primary
    plugin results this post-action plugin will be executed."""

    def should_run(self, plugin_results: list[PluginResult]) -> bool:
        """Return True if at least one condition is satisfied by *plugin_results*.

        An empty ``conditions`` list is treated as *never run* (returns False),
        which prevents post-action plugins from accidentally firing unconditionally
        when a config omits conditions.

        Args:
            plugin_results: The list of
                :class:`~nodescraper.models.pluginresult.PluginResult` objects
                produced by the primary plugin run.

        Returns:
            bool: True if this post-action plugin should be executed.
        """
        if not self.conditions:
            return False
        return any(condition.is_met(plugin_results) for condition in self.conditions)
