###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
#
###############################################################################
import argparse
import unittest

from nodescraper.cli.common_args import add_nodescraper_core_arguments
from nodescraper.cli.embed import (
    build_run_plugins_parsed_top_level,
    nodescraper_core_cli_dests,
)


class TestEmbeddingNamespace(unittest.TestCase):
    def test_core_dests_includes_expected_fields(self):
        dests = nodescraper_core_cli_dests()
        self.assertIn("sys_name", dests)
        self.assertIn("plugin_configs", dests)
        self.assertIn("connection_config", dests)

    def test_build_sets_subcmd_plugin_name_and_copies_core(self):
        p = argparse.ArgumentParser()
        add_nodescraper_core_arguments(p)
        ns = p.parse_args(
            [
                "--sys-name",
                "host-a",
                "--sys-location",
                "LOCAL",
                "--sys-interaction-level",
                "INTERACTIVE",
            ]
        )
        top = build_run_plugins_parsed_top_level(ns, "DmesgPlugin")
        self.assertEqual(top.subcmd, "run-plugins")
        self.assertEqual(top.plugin_name, "DmesgPlugin")
        self.assertEqual(top.sys_name, "host-a")

    def test_build_omits_plugin_name_for_bare_run_plugins(self):
        """Bare ``run-plugins`` (no plugin token) uses default config in :class:`NodeScraperCliApp`."""
        p = argparse.ArgumentParser()
        add_nodescraper_core_arguments(p)
        ns = p.parse_args(["--sys-name", "host-b", "--sys-location", "LOCAL"])
        top = build_run_plugins_parsed_top_level(ns, None)
        self.assertEqual(top.subcmd, "run-plugins")
        self.assertFalse(hasattr(top, "plugin_name"))
        self.assertEqual(top.sys_name, "host-b")

    def test_map_sys_interaction_level_optional(self):
        p = argparse.ArgumentParser()
        add_nodescraper_core_arguments(
            p,
            sys_interaction_level_choices=["SURFACE", "STANDARD", "DISRUPTIVE"],
        )
        ns = p.parse_args(["--sys-interaction-level", "STANDARD"])
        top = build_run_plugins_parsed_top_level(
            ns,
            "P",
            map_sys_interaction_level=lambda s: {"STANDARD": "INTERACTIVE"}.get(s, s),
        )
        self.assertEqual(top.sys_interaction_level, "INTERACTIVE")

    def test_build_copies_connection_config_dict_from_host(self):
        """``connection_config`` is a core dest; hosts may pre-build InBand JSON shape."""
        host = argparse.Namespace(
            sys_name="remote-host",
            sys_location="REMOTE",
            sys_interaction_level="INTERACTIVE",
            connection_config={
                "InBandConnectionManager": {
                    "hostname": "remote-host",
                    "username": "alice",
                    "port": 2222,
                }
            },
        )
        top = build_run_plugins_parsed_top_level(host, "DmesgPlugin")
        ib = top.connection_config["InBandConnectionManager"]
        self.assertEqual(ib["hostname"], "remote-host")
        self.assertEqual(ib["username"], "alice")
        self.assertEqual(ib["port"], 2222)


if __name__ == "__main__":
    unittest.main()
