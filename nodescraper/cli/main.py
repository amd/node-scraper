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

from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import Optional

from nodescraper.cli.app import NodeScraperCliApp
from nodescraper.cli.extension import CliExtension


def main(
    arg_input: Optional[list[str]] = None,
    *,
    parsed_top_level: Optional[argparse.Namespace] = None,
    plugin_arg_map: Optional[dict[str, list[str]]] = None,
    invalid_plugins: Optional[list[str]] = None,
    extensions: Sequence[CliExtension] = (),
) -> None:
    """Run the nodescraper CLI (may call ``sys.exit``).

    Args:
        arg_input: Argv tail when not using *parsed_top_level*.
        parsed_top_level: Skip ``process_args`` / top-level ``parse_args`` when embedding.
        plugin_arg_map: Per-plugin argv fragments when embedding.
        invalid_plugins: Unknown plugin names to warn about when embedding.
        extensions: :class:`~nodescraper.cli.extension.CliExtension` instances.
    """
    NodeScraperCliApp(extensions=tuple(extensions)).main(
        arg_input,
        parsed_top_level=parsed_top_level,
        plugin_arg_map=plugin_arg_map,
        invalid_plugins=invalid_plugins,
    )


def run_cli_main(
    arg_input: Optional[list[str]] = None,
    *,
    parsed_top_level: Optional[argparse.Namespace] = None,
    plugin_arg_map: Optional[dict[str, list[str]]] = None,
    invalid_plugins: Optional[list[str]] = None,
    extensions: Sequence[CliExtension] = (),
) -> int:
    """Run the CLI and return an exit code (converts :exc:`SystemExit` from :func:`main`).

    Args:
        Same as :func:`main`.

    Returns:
        Exit code (``0`` success; non-zero on error or early CLI exit).
    """
    try:
        main(
            arg_input,
            parsed_top_level=parsed_top_level,
            plugin_arg_map=plugin_arg_map,
            invalid_plugins=invalid_plugins,
            extensions=extensions,
        )
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        return 1
    return 0


if __name__ == "__main__":
    main()
