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
from typing import Any
from unittest.mock import patch

from nodescraper.connection.redfish import RedfishSshProxyConnectionManager
from nodescraper.enums import OSFamily, SystemLocation
from nodescraper.models import PluginConfig, SystemInfo
from nodescraper.pluginexecutor import PluginExecutor

PLUGIN = "RedfishEndpointPlugin"
OVERRIDE = "RedfishSshProxyConnectionManager"

PROXY_CONNECTION: dict[str, Any] = {
    OVERRIDE: {
        "host": "192.0.2.10",
        "ssh": {"hostname": "bmc", "username": "root", "password": "x"},
    }
}


def _executor(plugin_args: dict, connections: dict) -> PluginExecutor:
    return PluginExecutor(
        plugin_configs=[PluginConfig(plugins={PLUGIN: plugin_args})],
        connections=connections,
        system_info=SystemInfo(
            name="test", location=SystemLocation.REMOTE, os_family=OSFamily.LINUX
        ),
    )


class TestPluginConnectionOverride(unittest.TestCase):
    def test_override_uses_configured_manager(self):
        ex = _executor({"connection": OVERRIDE}, PROXY_CONNECTION)
        plugin_cls = ex.plugin_registry.plugins[PLUGIN]
        self.assertIsNot(plugin_cls.CONNECTION_TYPE, RedfishSshProxyConnectionManager)

        cm = ex._get_connection_manager_for_plugin(plugin_cls, PLUGIN, connection_override=OVERRIDE)

        self.assertIs(cm, ex.connection_library[RedfishSshProxyConnectionManager])

    def test_unregistered_name_returns_none(self):
        ex = _executor({}, {})
        plugin_cls = ex.plugin_registry.plugins[PLUGIN]
        self.assertIsNone(
            ex._get_connection_manager_for_plugin(
                plugin_cls, PLUGIN, connection_override="NotARealManager"
            )
        )

    def test_registered_but_unconfigured_returns_none(self):
        ex = _executor({}, {})
        plugin_cls = ex.plugin_registry.plugins[PLUGIN]
        self.assertIsNone(
            ex._get_connection_manager_for_plugin(plugin_cls, PLUGIN, connection_override=OVERRIDE)
        )

    def test_connection_key_not_passed_to_run(self):
        ex = _executor(
            {"collection": False, "analysis": False, "connection": OVERRIDE},
            PROXY_CONNECTION,
        )
        plugin_cls = ex.plugin_registry.plugins[PLUGIN]

        with patch.object(plugin_cls, "run", autospec=True) as mock_run:
            ran = ex._run_single_plugin(
                PLUGIN, ex.plugin_config.plugins[PLUGIN], [], queue_callback=None
            )

        self.assertTrue(ran)
        self.assertNotIn("connection", mock_run.call_args.kwargs)


if __name__ == "__main__":
    unittest.main()
