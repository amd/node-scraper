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
"""Functional tests for GenericCollectionPlugin with --plugin-configs."""

import csv
from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir():
    """Return path to fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def generic_collection_config_file(fixtures_dir):
    """Return path to GenericCollectionPlugin config file."""
    return fixtures_dir / "generic_collection_plugin_config.json"


def test_generic_collection_plugin_with_config_file(
    run_cli_command, generic_collection_config_file, tmp_path
):
    """Run GenericCollectionPlugin using collection_args.commands from config file."""
    assert (
        generic_collection_config_file.exists()
    ), f"Config file not found: {generic_collection_config_file}"

    log_path = str(tmp_path / "logs_generic_collection")
    result = run_cli_command(
        [
            "--log-path",
            log_path,
            f"--plugin-configs={generic_collection_config_file}",
            "run-plugins",
            "GenericCollectionPlugin",
        ],
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode in [0, 1, 2]
    assert "GenericCollectionPlugin" in output
    assert "Generic collection" in output or "genericcollection" in output.lower()


def test_generic_collection_plugin_csv_status_ok(
    run_cli_command, generic_collection_config_file, tmp_path
):
    """Configured commands should collect successfully on the local system."""
    log_path = str(tmp_path / "logs_generic_collection_csv")
    result = run_cli_command(
        [
            "--log-path",
            log_path,
            f"--plugin-configs={generic_collection_config_file}",
            "run-plugins",
            "GenericCollectionPlugin",
        ],
        check=False,
    )

    output = result.stdout + result.stderr
    assert "GenericCollectionPlugin" in output

    csv_files = list(Path(log_path).glob("**/nodescraper.csv"))
    if not csv_files:
        pytest.skip("CSV output not written; cannot verify collection status")

    with open(csv_files[0], "r", encoding="utf-8") as csv_file:
        rows = [
            row
            for row in csv.DictReader(csv_file)
            if row.get("plugin") == "GenericCollectionPlugin"
        ]

    assert len(rows) >= 1, "GenericCollectionPlugin should appear in CSV results"
    assert rows[0].get("status") == "OK", rows[0].get("message")
    assert "6/6 commands succeeded" in (rows[0].get("message") or "")


def test_generic_collection_plugin_without_commands_not_ran(run_cli_command, tmp_path):
    """Running without collection_args.commands should report no commands configured."""
    log_path = str(tmp_path / "logs_generic_collection_empty")
    result = run_cli_command(
        ["--log-path", log_path, "run-plugins", "GenericCollectionPlugin"],
        check=False,
    )

    output = result.stdout + result.stderr
    assert result.returncode in [0, 1, 2]
    assert "GenericCollectionPlugin" in output
    assert "No commands configured" in output or "NOT_RAN" in output
