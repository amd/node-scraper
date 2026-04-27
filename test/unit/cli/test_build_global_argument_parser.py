# Copyright (C) 2025 Advanced Micro Devices, Inc.

from __future__ import annotations

from nodescraper.cli.cli import build_global_argument_parser


def test_build_global_argument_parser_leaves_subcommand_in_unknown() -> None:
    p = build_global_argument_parser(add_help=False)
    ns, rest = p.parse_known_args(["--sys-name", "sut.example", "run-plugins", "DmesgPlugin"])
    assert ns.sys_name == "sut.example"
    assert rest == ["run-plugins", "DmesgPlugin"]


def test_build_global_argument_parser_has_no_subcmd_default() -> None:
    p = build_global_argument_parser(add_help=False)
    ns, _ = p.parse_known_args([])
    assert getattr(ns, "subcmd", None) is None
