###############################################################################
#
# MIT License
#
# Copyright (C) 2026 Advanced Micro Devices, Inc.
#
###############################################################################

from __future__ import annotations

import argparse

from nodescraper.cli.host_cli_embed import (
    apply_host_cli_args_to_parsed_args,
    merge_plugin_connection_config_from_host_ns,
)


def test_apply_host_cli_args_to_parsed_args_copies_sys_fields() -> None:
    parsed = argparse.Namespace(
        sys_name="client",
        sys_location="LOCAL",
        sys_sku=None,
        sys_platform=None,
        sys_interaction_level="INTERACTIVE",
    )
    host = argparse.Namespace(
        sys_name="sut.example.com",
        sys_location="REMOTE",
        sys_sku="MI450",
        sys_platform="whitman",
        sys_interaction_level="STANDARD",
    )
    apply_host_cli_args_to_parsed_args(parsed, host)
    assert parsed.sys_name == "sut.example.com"
    assert parsed.sys_location == "REMOTE"
    assert parsed.sys_sku == "MI450"
    assert parsed.sys_platform == "whitman"
    assert parsed.sys_interaction_level == "STANDARD"


def test_apply_host_cli_args_to_parsed_args_noop_without_host() -> None:
    parsed = argparse.Namespace(sys_name="x")
    apply_host_cli_args_to_parsed_args(parsed, None)
    assert parsed.sys_name == "x"


def test_merge_plugin_connection_config_from_host_ns_host_first_cli_wins() -> None:
    parsed = argparse.Namespace(
        connection_config={"InBandConnectionManager": {"hostname": "cli-host"}}
    )
    host = argparse.Namespace(
        connection_config={
            "InBandConnectionManager": {"hostname": "host-host"},
            "RedfishConnectionManager": {"host": "10.0.0.1"},
        }
    )
    merge_plugin_connection_config_from_host_ns(parsed, host)
    assert parsed.connection_config["InBandConnectionManager"]["hostname"] == "cli-host"
    assert parsed.connection_config["RedfishConnectionManager"]["host"] == "10.0.0.1"


def test_merge_plugin_connection_config_from_host_ns_host_only() -> None:
    parsed = argparse.Namespace(connection_config=None)
    host = argparse.Namespace(
        connection_config={"InBandConnectionManager": {"hostname": "h", "username": "u"}}
    )
    merge_plugin_connection_config_from_host_ns(parsed, host)
    assert parsed.connection_config == {
        "InBandConnectionManager": {"hostname": "h", "username": "u"}
    }
