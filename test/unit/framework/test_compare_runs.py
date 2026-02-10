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
import logging

from nodescraper.cli.compare_runs import (
    _diff_value,
    _format_value,
    run_compare_runs,
)
from nodescraper.pluginregistry import PluginRegistry


def test_diff_value_empty_dicts():
    """Same empty dicts produce no diffs."""
    assert _diff_value({}, {}, "") == []


def test_diff_value_identical_dicts():
    """Identical dicts produce no diffs."""
    d = {"a": 1, "b": "x"}
    assert _diff_value(d, d, "") == []


def test_diff_value_different_scalar():
    """Different scalar values produce one diff."""
    diffs = _diff_value(1, 2, "ver")
    assert len(diffs) == 1
    assert diffs[0] == ("ver", 1, 2)


def test_diff_value_key_only_in_first():
    """Key missing in second run is reported."""
    diffs = _diff_value({"a": 1, "b": 2}, {"a": 1}, "")
    assert len(diffs) == 1
    assert diffs[0][0] == "b"
    assert diffs[0][1] == 2
    assert diffs[0][2] is None


def test_diff_value_key_only_in_second():
    """Key missing in first run is reported."""
    diffs = _diff_value({"a": 1}, {"a": 1, "b": 2}, "")
    assert len(diffs) == 1
    assert diffs[0][0] == "b"
    assert diffs[0][1] is None
    assert diffs[0][2] == 2


def test_diff_value_nested_dict():
    """Nested dict differences are reported with path."""
    d1 = {"a": {"x": 1}}
    d2 = {"a": {"x": 2}}
    diffs = _diff_value(d1, d2, "")
    assert len(diffs) == 1
    assert diffs[0] == ("a.x", 1, 2)


def test_diff_value_list_same():
    """Identical lists produce no diffs."""
    assert _diff_value([1, 2], [1, 2], "list") == []


def test_diff_value_list_different_length():
    """List length difference is reported."""
    diffs = _diff_value([1, 2], [1, 2, 3], "arr")
    assert len(diffs) == 1
    assert diffs[0][0] == "arr[2]"
    assert diffs[0][1] is None
    assert diffs[0][2] == 3


def test_diff_value_list_different_element():
    """Different list element is reported."""
    diffs = _diff_value([1, 2], [1, 99], "arr")
    assert len(diffs) == 1
    assert diffs[0] == ("arr[1]", 2, 99)


def test_format_value_none():
    """None formats as <missing>."""
    assert _format_value(None) == "<missing>"


def test_format_value_short_string():
    """Short value is unchanged."""
    assert _format_value("ok") == "'ok'"


def test_format_value_long_truncated():
    """Long value is truncated."""
    long_str = "x" * 100
    out = _format_value(long_str, max_len=50)
    assert len(out) == 50
    assert out.endswith("...")


def test_run_compare_runs_no_data(caplog, tmp_path):
    """When neither run has plugin data, warning is logged."""
    logger = logging.getLogger("test_compare_runs")
    plugin_reg = PluginRegistry()
    run_compare_runs(str(tmp_path / "run1"), str(tmp_path / "run2"), plugin_reg, logger)
    assert "No plugin data found" in caplog.text


def test_run_compare_runs_with_fixture_dirs(caplog, framework_fixtures_path):
    """With two log dirs using fixture (same content), table is produced and no diffs."""
    logger = logging.getLogger("test_compare_runs")
    plugin_reg = PluginRegistry()
    base = framework_fixtures_path / "log_dir"
    run_compare_runs(str(base), str(base), plugin_reg, logger)
    assert "Loading run 1" in caplog.text
    assert "Loading run 2" in caplog.text
    # Same dir twice: BiosPlugin should be found, no differences
    assert "Plugin" in caplog.text
    assert "No differences" in caplog.text or "difference" in caplog.text.lower()


def test_run_compare_runs_one_run_missing_plugin(caplog, framework_fixtures_path, tmp_path):
    """When a plugin exists only in run1, NOT_RAN message for run2 is in results."""
    logger = logging.getLogger("test_compare_runs")
    plugin_reg = PluginRegistry()
    run1 = framework_fixtures_path / "log_dir"
    run2 = tmp_path / "run2"
    run2.mkdir()
    # run2 has no collector dirs
    run_compare_runs(str(run1), str(run2), plugin_reg, logger)
    assert "Loading run 1" in caplog.text
    assert "Loading run 2" in caplog.text
    # BiosPlugin in run1 only -> we should see "not found in run 2"
    assert "not found in run 2" in caplog.text or "NOT_RAN" in caplog.text
