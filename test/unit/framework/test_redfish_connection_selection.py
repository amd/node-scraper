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

from nodescraper.connection.redfish import (
    RedfishConnectionManager,
    RedfishSshProxyConnectionManager,
)
from nodescraper.enums import OSFamily, SystemLocation
from nodescraper.interfaces import ConnectionManager
from nodescraper.models import PluginConfig, SystemInfo
from nodescraper.pluginexecutor import PluginExecutor

REDFISH_PLUGIN = "RedfishEndpointPlugin"
PROXY_PLUGIN = "AmcRedfishDiagPlugin"

DIRECT_CONFIG: dict[str, Any] = {
    "RedfishConnectionManager": {"host": "bmc.example.com", "username": "root", "password": "x"}
}
PROXY_CONFIG: dict[str, Any] = {
    "RedfishSshProxyConnectionManager": {
        "host": "192.0.2.10",
        "ssh": {"hostname": "bmc.example.com", "username": "root", "password": "x"},
    }
}
BOTH_CONFIG: dict[str, Any] = {**DIRECT_CONFIG, **PROXY_CONFIG}


def _executor(connections: dict) -> PluginExecutor:
    return PluginExecutor(
        plugin_configs=[PluginConfig(plugins={REDFISH_PLUGIN: {}})],
        connections=connections,
        system_info=SystemInfo(
            name="test", location=SystemLocation.REMOTE, os_family=OSFamily.LINUX
        ),
    )


def _resolve(ex: PluginExecutor, plugin_name: str = REDFISH_PLUGIN) -> Optional[ConnectionManager]:
    plugin_cls = ex.plugin_registry.plugins[plugin_name]
    return ex._get_connection_manager_for_plugin(plugin_cls, plugin_name)


class TestRedfishConnectionSelection(unittest.TestCase):
    def test_plugin_declares_direct_redfish(self):
        ex = _executor({})
        plugin_cls = ex.plugin_registry.plugins[REDFISH_PLUGIN]
        self.assertIs(plugin_cls.CONNECTION_TYPE, RedfishConnectionManager)

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
            ex._run_single_plugin(
                REDFISH_PLUGIN, ex.plugin_config.plugins[REDFISH_PLUGIN], [], queue_callback=None
            )
        )

    def test_plugin_declaring_proxy_keeps_proxy_when_both_configured(self):
        ex = _executor(BOTH_CONFIG)
        plugin_cls = ex.plugin_registry.plugins[PROXY_PLUGIN]
        self.assertIs(plugin_cls.CONNECTION_TYPE, RedfishSshProxyConnectionManager)
        self.assertIs(
            _resolve(ex, PROXY_PLUGIN), ex.connection_library[RedfishSshProxyConnectionManager]
        )


if __name__ == "__main__":
    unittest.main()
