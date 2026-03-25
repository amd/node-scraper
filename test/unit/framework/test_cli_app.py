###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
#
###############################################################################
"""Tests for :class:`~nodescraper.cli.app.NodeScraperCliApp` and :class:`~nodescraper.cli.extension.CliExtension`."""

import argparse

from nodescraper.cli.app import NodeScraperCliApp
from nodescraper.cli.extension import CliExtension


class _HostFlagExtension(CliExtension):
    def alter_cli_parser(
        self,
        *,
        root_parser: argparse.ArgumentParser,
        subparsers,
        run_plugins_parser: argparse.ArgumentParser,
        plugin_reg,
        config_reg,
        plugin_subparser_map,
    ) -> None:
        run_plugins_parser.add_argument(
            "--host-smoke-flag",
            action="store_true",
            help="Test-only flag from CliExtension",
        )


def _subparser(parser: argparse.ArgumentParser, name: str) -> argparse.ArgumentParser:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices[name]
    raise AssertionError("subparser not found")


def test_cli_extension_alter_run_plugins_parser():
    app = NodeScraperCliApp(extensions=(_HostFlagExtension(),))
    run_plugins = _subparser(app.parser, "run-plugins")
    dests = {a.dest for a in run_plugins._actions if hasattr(a, "dest")}
    assert "host_smoke_flag" in dests
