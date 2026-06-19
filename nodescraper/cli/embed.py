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
from collections.abc import Sequence
from typing import Optional

from nodescraper.cli.cli import get_cli_top_level_subcommands
from nodescraper.interfaces import TaskResultHook

CLI_TOP_LEVEL_SUBCOMMANDS = get_cli_top_level_subcommands()

__all__ = [
    "CLI_TOP_LEVEL_SUBCOMMANDS",
    "get_cli_top_level_subcommands",
    "run_cli_return_code",
    "run_main_return_code",
]


def run_cli_return_code(
    argv: list[str],
    *,
    host_cli_args: Optional[argparse.Namespace] = None,
    embed_default_task_result_hooks: Optional[Sequence[TaskResultHook]] = None,
) -> int:
    """Run nodescraper in-process; same behavior as :func:`run_main_return_code`.

    Args:
        argv: Tokens after the program name.
        host_cli_args: Optional host namespace forwarded to :func:`nodescraper.cli.cli.main`.
        embed_default_task_result_hooks: Optional hooks prepended to every plugin run and connection
            manager for this embed (e.g. host event logging). Merged in :class:`PluginExecutor`.

    Returns:
        Integer exit code (``SystemExit`` is mapped, not raised).
    """
    return run_main_return_code(
        argv,
        host_cli_args=host_cli_args,
        embed_default_task_result_hooks=embed_default_task_result_hooks,
    )


def run_main_return_code(
    arg_input: list[str],
    *,
    host_cli_args: Optional[argparse.Namespace] = None,
    embed_default_task_result_hooks: Optional[Sequence[TaskResultHook]] = None,
) -> int:
    """Run :func:`nodescraper.cli.cli.main` and map ``SystemExit`` to an exit code.

    Args:
        arg_input: Tokens after the program name.
        host_cli_args: Optional host namespace for embedded runs.
        embed_default_task_result_hooks: Optional default task-result hooks for this embed.

    Returns:
        Integer exit code.
    """
    from nodescraper.cli.cli import main

    try:
        main(
            arg_input,
            host_cli_args=host_cli_args,
            embed_default_task_result_hooks=embed_default_task_result_hooks,
        )
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        return 1
    return 0
