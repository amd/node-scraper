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
