###############################################################################
#
# MIT License
#
# Copyright (C) 2026 Advanced Micro Devices, Inc.
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

from __future__ import annotations

import argparse
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator, Optional

from nodescraper.models import PluginConfig, SystemInfo
from nodescraper.models.pluginresult import PluginResult
from nodescraper.pluginexecutor import PluginExecutor
from nodescraper.pluginregistry import PluginRegistry

_plugin_run_invocation_ctx: ContextVar[Optional["PluginRunInvocation"]] = ContextVar(
    "nodescraper_plugin_run_invocation", default=None
)


def get_plugin_run_invocation() -> Optional[PluginRunInvocation]:
    """Return the active invocation while run_plugin_queue_with_invocation is running, if any."""
    return _plugin_run_invocation_ctx.get()


@contextmanager
def plugin_run_invocation_scope(inv: PluginRunInvocation) -> Iterator[None]:
    """Bind *inv* for nested code (connection managers, plugins) for the scope of the context."""
    token = _plugin_run_invocation_ctx.set(inv)
    try:
        yield
    finally:
        _plugin_run_invocation_ctx.reset(token)


@dataclass
class PluginRunInvocation:
    """Recorded inputs for one plugin run; optional host_cli_args for embedded hosts."""

    plugin_reg: PluginRegistry
    parsed_args: argparse.Namespace
    plugin_config_inst_list: list[PluginConfig]
    system_info: SystemInfo
    log_path: Optional[str]
    logger: logging.Logger
    timestamp: str
    sname: str
    host_cli_args: Optional[argparse.Namespace] = None
    session_id: Optional[str] = None


def run_plugin_queue_with_invocation(
    *,
    plugin_reg: PluginRegistry,
    parsed_args: argparse.Namespace,
    plugin_config_inst_list: list[PluginConfig],
    system_info: SystemInfo,
    log_path: Optional[str],
    logger: logging.Logger,
    timestamp: str,
    sname: str,
    host_cli_args: Optional[argparse.Namespace] = None,
    session_id: Optional[str] = None,
) -> list[PluginResult]:
    """Constructs the plugin executor, binds invocation context, and runs the plugin queue."""
    inv = PluginRunInvocation(
        plugin_reg=plugin_reg,
        parsed_args=parsed_args,
        plugin_config_inst_list=plugin_config_inst_list,
        system_info=system_info,
        log_path=log_path,
        logger=logger,
        timestamp=timestamp,
        sname=sname,
        host_cli_args=host_cli_args,
        session_id=session_id,
    )
    plugin_executor = PluginExecutor(
        logger=logger,
        plugin_configs=plugin_config_inst_list,
        connections=parsed_args.connection_config,
        system_info=system_info,
        log_path=log_path,
        plugin_registry=plugin_reg,
        session_id=session_id,
    )
    with plugin_run_invocation_scope(inv):
        return plugin_executor.run_queue()


__all__ = [
    "PluginRunInvocation",
    "get_plugin_run_invocation",
    "plugin_run_invocation_scope",
    "run_plugin_queue_with_invocation",
]
