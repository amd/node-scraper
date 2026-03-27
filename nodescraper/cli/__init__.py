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

from .app import NodeScraperCliApp
from .common_args import (
    add_nodescraper_core_arguments,
    build_nodescraper_core_parent_parser,
)
from .embed import (
    build_run_plugins_parsed_top_level,
    nodescraper_core_cli_dests,
    run_cli_embedded,
)
from .extension import CliExtension
from .host_integration import build_cli_parser, register_nodescraper_cli_subcommands
from .invocation import PluginRunInvocation
from .main import main as cli_entry
from .main import run_cli_main
from .prefer_distribution_extension import PreferDistributionPluginsExtension

__all__ = [
    "CliExtension",
    "NodeScraperCliApp",
    "PluginRunInvocation",
    "PreferDistributionPluginsExtension",
    "add_nodescraper_core_arguments",
    "build_cli_parser",
    "register_nodescraper_cli_subcommands",
    "build_nodescraper_core_parent_parser",
    "build_run_plugins_parsed_top_level",
    "cli_entry",
    "nodescraper_core_cli_dests",
    "run_cli_embedded",
    "run_cli_main",
]
