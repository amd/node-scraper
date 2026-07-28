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
import argparse
import os

import pytest

from nodescraper.cli.multi_node import (
    _plugin_results_exit_code,
    _summarize_plugin_results,
    build_run_log_dir,
    is_multi_target_connection_config,
    normalize_sname,
    parse_multi_target_connection_config,
)
from nodescraper.enums import ExecutionStatus
from nodescraper.models.pluginresult import PluginResult


def test_is_multi_target_connection_config():
    assert not is_multi_target_connection_config(None)
    assert not is_multi_target_connection_config({"InBandConnectionManager": {}})
    assert is_multi_target_connection_config({"targets": [{"name": "a"}]})


def test_normalize_sname():
    assert normalize_sname("Node-A.example.com") == "node_a_example_com"


def test_parse_multi_target_connection_config():
    config = {
        "targets": [
            {
                "name": "node-a",
                "sys_location": "REMOTE",
                "InBandConnectionManager": {"hostname": "a.example.com", "username": "u"},
            },
            {
                "RedfishConnectionManager": {
                    "host": "10.0.0.2",
                    "username": "ADMIN",
                }
            },
        ]
    }
    targets = parse_multi_target_connection_config(
        config,
        default_sys_location="LOCAL",
    )
    assert len(targets) == 2
    assert targets[0].name == "node-a"
    assert targets[0].sys_location == "REMOTE"
    assert "InBandConnectionManager" in targets[0].connection_config
    assert targets[1].name == "10.0.0.2"
    assert targets[1].sys_location == "LOCAL"


def test_infer_target_name_from_oob_ssh_manager_key():
    config = {
        "targets": [
            {
                "OobSshConnectionManager": {
                    "host": "10.0.0.99",
                    "username": "root",
                }
            }
        ]
    }
    targets = parse_multi_target_connection_config(
        config,
        default_sys_location="LOCAL",
    )
    assert targets[0].name == "10.0.0.99"


def test_parse_multi_target_rejects_mixed_top_level_managers():
    config = {
        "InBandConnectionManager": {"hostname": "x", "username": "u"},
        "targets": [
            {"name": "node-a", "RedfishConnectionManager": {"host": "1.1.1.1", "username": "u"}}
        ],
    }
    with pytest.raises(argparse.ArgumentTypeError):
        parse_multi_target_connection_config(config, default_sys_location="LOCAL")


def test_parse_multi_target_requires_connection_section():
    with pytest.raises(argparse.ArgumentTypeError):
        parse_multi_target_connection_config(
            {"targets": [{"name": "empty-node"}]},
            default_sys_location="LOCAL",
        )


def test_build_run_log_dir(tmp_path):
    run_dir = build_run_log_dir(str(tmp_path), "Node-A", "2026_01_01-12_00_00_AM")
    assert run_dir == os.path.join(
        tmp_path,
        "scraper_logs_node_a_2026_01_01-12_00_00_AM",
    )
    assert os.path.isdir(run_dir)


def test_worker_plugin_registry_is_cached():
    from nodescraper.cli import multi_node

    multi_node._reset_worker_plugin_registry_cache()
    first = multi_node._get_worker_plugin_registry()
    second = multi_node._get_worker_plugin_registry()
    assert first is second
    multi_node._reset_worker_plugin_registry_cache()


def test_plugin_results_exit_code_treats_not_ran_as_failure() -> None:
    results = [
        PluginResult(
            status=ExecutionStatus.NOT_RAN,
            source="ServiceabilityPluginMI3XX",
            message="Plugin tasks not ran",
        )
    ]
    assert _plugin_results_exit_code(results) == 1


def test_plugin_results_exit_code_ok_and_warning_succeed() -> None:
    results = [
        PluginResult(status=ExecutionStatus.OK, source="PluginA"),
        PluginResult(status=ExecutionStatus.WARNING, source="PluginB"),
    ]
    assert _plugin_results_exit_code(results) == 0


def test_summarize_plugin_results() -> None:
    results = [
        PluginResult(status=ExecutionStatus.NOT_RAN, source="ServiceabilityPluginMI3XX"),
    ]
    assert _summarize_plugin_results(results) == "ServiceabilityPluginMI3XX=NOT_RAN"
