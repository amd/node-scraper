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
from typing import Optional

__all__ = [
    "apply_host_cli_args_to_parsed_args",
    "merge_plugin_connection_config_from_host_ns",
]


def apply_host_cli_args_to_parsed_args(
    parsed_args: argparse.Namespace,
    host_ns: Optional[argparse.Namespace],
) -> None:
    """Copy host profile fields from an embedding host onto parsed top-level args."""
    if host_ns is None:
        return
    for attr in (
        "sys_name",
        "sys_location",
        "sys_sku",
        "sys_platform",
        "sys_interaction_level",
    ):
        if hasattr(host_ns, attr):
            val = getattr(host_ns, attr)
            if val is not None:
                setattr(parsed_args, attr, val)


def merge_plugin_connection_config_from_host_ns(
    parsed_args: argparse.Namespace,
    host_ns: Optional[argparse.Namespace],
) -> None:
    """Merge plugin ``connection_config`` from the host namespace into ``parsed_args``.

    The same key shape as ``--connection-config`` on the node-scraper argv:
    connection manager class name (string) → args dict. When both the host
    profile and the CLI supply ``connection_config``, **CLI** values win for
    duplicate manager keys.
    """
    if host_ns is None:
        return
    from_host = getattr(host_ns, "connection_config", None)
    if not from_host:
        return
    if not isinstance(from_host, dict):
        return
    from_cli = getattr(parsed_args, "connection_config", None) or {}
    if not isinstance(from_cli, dict):
        from_cli = {}
    parsed_args.connection_config = {**from_host, **from_cli}
