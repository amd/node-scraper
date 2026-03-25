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
"""Host extension hooks for the node-scraper CLI."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nodescraper.configregistry import ConfigRegistry
    from nodescraper.pluginregistry import PluginRegistry

CLI_EXTENSION_API = 1


class CliExtension:
    """Optional hooks; default implementations are no-ops.

    Override :meth:`prepare_registries` to merge entry points, register connection managers, etc.
    Override :meth:`alter_cli_parser` to add flags to the root parser or ``run-plugins`` parser.
    """

    def prepare_registries(
        self,
        plugin_reg: PluginRegistry,
        config_reg: ConfigRegistry,
    ) -> None:
        """Invoked once after default registries are constructed, before :func:`build_cli_parser`."""

    def alter_cli_parser(
        self,
        *,
        root_parser: argparse.ArgumentParser,
        subparsers: Any,
        run_plugins_parser: argparse.ArgumentParser,
        plugin_reg: PluginRegistry,
        config_reg: ConfigRegistry,
        plugin_subparser_map: dict[str, tuple[argparse.ArgumentParser, dict]],
    ) -> None:
        """Invoked after native subcommands and per-plugin nested parsers are registered."""


__all__ = ["CLI_EXTENSION_API", "CliExtension"]
