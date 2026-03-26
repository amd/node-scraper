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
"""Typed bundle for the plugin-executor phase of the CLI (after argparse)."""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from typing import Optional

from nodescraper.models import PluginConfig, SystemInfo
from nodescraper.pluginregistry import PluginRegistry


@dataclass
class PluginRunInvocation:
    """Everything needed to construct :class:`~nodescraper.pluginexecutor.PluginExecutor` and finish the run.

    Built by :meth:`nodescraper.cli.app.NodeScraperCliApp.prepare_plugin_run`; consumed by
    :meth:`nodescraper.cli.app.NodeScraperCliApp.execute_plugin_run`.
    """

    plugin_reg: PluginRegistry
    parsed_args: argparse.Namespace
    plugin_config_inst_list: list[PluginConfig]
    system_info: SystemInfo
    log_path: Optional[str]
    logger: logging.Logger
    timestamp: str
    sname: str


__all__ = ["PluginRunInvocation"]
