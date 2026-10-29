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
import unittest
from typing import Any, Optional
from unittest.mock import patch

from nodescraper.connection.redfish import (
    RedfishConnectionManager,
    RedfishSshProxyConnectionManager,
)
from nodescraper.enums import OSFamily, SystemLocation
from nodescraper.interfaces import ConnectionManager
from nodescraper.models import PluginConfig, SystemInfo
from nodescraper.pluginexecutor import PluginExecutor

PLUGIN = "RedfishEndpointPlugin"
DIRECT = "RedfishConnectionManager"
PROXY = "RedfishSshProxyConnectionManager"

DIRECT_CONFIG: dict[str, Any] = {
    DIRECT: {"host": "bmc.example.com", "username": "root", "password": "x"}
}
PROXY_CONFIG: dict[str, Any] = {
    PROXY: {
        "host": "192.0.2.10",
        "ssh": {"hostname": "bmc.example.com", "username": "root", "password": "x"},
    }
}
BOTH_CONFIG: dict[str, Any] = {**DIRECT_CONFIG, **PROXY_CONFIG}


def _executor(connections: dict, plugin_args: Optional[dict] = None) -> PluginExecutor:
    return PluginExecutor(
        plugin_configs=[PluginConfig(plugins={PLUGIN: plugin_args or {}})],
        connections=connections,
        system_info=SystemInfo(
            name="test", location=SystemLocation.REMOTE, os_family=OSFamily.LINUX
        ),
    )


def _resolve(ex: PluginExecutor, override: Optional[str] = None) -> Optional[ConnectionManager]:
    plugin_cls = ex.plugin_registry.plugins[PLUGIN]
    return ex._get_connection_manager_for_plugin(plugin_cls, PLUGIN, connection_override=override)


class TestRedfishConnectionSelection(unittest.TestCase):
    def test_plugin_declares_direct_redfish(self):
        ex = _executor({})
        self.assertIs(ex.plugin_registry.plugins[PLUGIN].CONNECTION_TYPE, RedfishConnectionManager)

    def test_direct_only_uses_direct(self):
        ex = _executor(DIRECT_CONFIG)
        self.assertIs(_resolve(ex), ex.connection_library[RedfishConnectionManager])

    def test_proxy_only_falls_back_to_proxy(self):
        ex = _executor(PROXY_CONFIG)
        self.assertIs(_resolve(ex), ex.connection_library[RedfishSshProxyConnectionManager])

    def test_both_prefers_direct(self):
        ex = _executor(BOTH_CONFIG)
        self.assertIs(_resolve(ex), ex.connection_library[RedfishConnectionManager])

    def test_neither_skips_plugin(self):
        ex = _executor({})
        self.assertIsNone(_resolve(ex))
        self.assertNotIn(RedfishConnectionManager, ex.connection_library)
        self.assertFalse(
            ex._run_single_plugin(PLUGIN, ex.plugin_config.plugins[PLUGIN], [], queue_callback=None)
        )


class TestPluginConnectionOverride(unittest.TestCase):
    def test_override_forces_proxy_when_both_configured(self):
        ex = _executor(BOTH_CONFIG)
        self.assertIs(_resolve(ex, PROXY), ex.connection_library[RedfishSshProxyConnectionManager])

    def test_unregistered_name_returns_none(self):
        ex = _executor(BOTH_CONFIG)
        self.assertIsNone(_resolve(ex, "NotARealManager"))

    def test_registered_but_unconfigured_returns_none(self):
        ex = _executor(DIRECT_CONFIG)
        self.assertIsNone(_resolve(ex, PROXY))

    def test_connection_key_not_passed_to_run(self):
        ex = _executor(BOTH_CONFIG, {"collection": False, "analysis": False, "connection": PROXY})
        plugin_cls = ex.plugin_registry.plugins[PLUGIN]

        with patch.object(plugin_cls, "run", autospec=True) as mock_run:
            ran = ex._run_single_plugin(
                PLUGIN, ex.plugin_config.plugins[PLUGIN], [], queue_callback=None
            )

        self.assertTrue(ran)
        self.assertNotIn("connection", mock_run.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
