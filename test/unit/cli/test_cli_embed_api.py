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

import pytest

from nodescraper.cli.cli import get_cli_top_level_subcommands
from nodescraper.cli.embed import (
    CLI_TOP_LEVEL_SUBCOMMANDS,
    run_cli_return_code,
    run_main_return_code,
)


def test_get_cli_top_level_subcommands_matches_argparse_subparsers() -> None:
    subs = get_cli_top_level_subcommands()
    assert isinstance(subs, tuple)
    assert "run-plugins" in subs
    assert "summary" in subs
    assert all(isinstance(s, str) for s in subs)


def test_cli_top_level_subcommands_lazy_alias_matches_getter() -> None:
    assert CLI_TOP_LEVEL_SUBCOMMANDS == get_cli_top_level_subcommands()


def test_run_cli_return_code_and_run_main_return_code_delegate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[list[str]] = []

    def fake_main(arg_input: list[str], *, host_cli_args=None) -> None:
        calls.append(list(arg_input))
        raise SystemExit(7)

    monkeypatch.setattr("nodescraper.cli.cli.main", fake_main)
    assert run_cli_return_code(["describe", "plugin", "X"]) == 7
    assert run_main_return_code(["a", "b"]) == 7
    assert calls == [["describe", "plugin", "X"], ["a", "b"]]
