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

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def generic_collection_config_file():
    """Return path to GenericCollectionPlugin demo config (functional fixtures)."""
    return _FIXTURES / "generic_collection_plugin_config.json"


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


def test_generic_collection_plugin_demo_config_runs_end_to_end(
    run_cli_command, generic_collection_config_file, tmp_path
):
    """Demo fixture config runs collection and analysis with expected partial failures."""
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
    assert "14/14 commands succeeded" not in output
    assert "14/14 checks passed" not in output
    assert "/14 commands succeeded" in output
    assert "/14 checks passed" in output
    assert "Check failed: kernel_os" in output

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
    assert rows[0].get("status") == "ERROR", rows[0].get("message")


def test_generic_collection_plugin_runs_analyzer(
    run_cli_command, generic_collection_config_file, tmp_path
):
    """Analysis checks from the demo fixture config should run after collection."""
    log_path = str(tmp_path / "logs_generic_collection_analysis")
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
    assert "Running data analyzer: GenericAnalyzer" in output
    assert "Generic analysis:" in output
    assert "14/14 checks passed" not in output
    assert "Check failed: kernel_os" in output


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
