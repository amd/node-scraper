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
from nodescraper.cli.host_namespace import (
    build_run_plugins_parsed_top_level,
    nodescraper_core_cli_dests,
)


class TestHostNamespace(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
