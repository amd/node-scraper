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
import pytest

from nodescraper.enums import ExecutionStatus
from nodescraper.plugins.inband.sys_settings.analyzer_args import (
    SysfsCheck,
    SysSettingsAnalyzerArgs,
)
from nodescraper.plugins.inband.sys_settings.sys_settings_analyzer import (
    SysSettingsAnalyzer,
)
from nodescraper.plugins.inband.sys_settings.sys_settings_data import (
    SysSettingsDataModel,
)

SYSFS_BASE = "/sys/kernel/mm/transparent_hugepage"


@pytest.fixture
def analyzer(system_info):
    return SysSettingsAnalyzer(system_info=system_info)


@pytest.fixture
def sample_data():
    return SysSettingsDataModel(
        readings={
            f"{SYSFS_BASE}/enabled": "always",
            f"{SYSFS_BASE}/defrag": "madvise",
        }
    )


def test_analyzer_no_checks_ok(analyzer, sample_data):
    """No checks configured -> OK."""
    result = analyzer.analyze_data(sample_data)
    assert result.status == ExecutionStatus.OK
    assert "No checks" in result.message


def test_analyzer_checks_match(analyzer, sample_data):
    """Checks match collected values -> OK."""
    args = SysSettingsAnalyzerArgs(
        checks=[
            SysfsCheck(
                path=f"{SYSFS_BASE}/enabled", expected=["always", "[always]"], name="enabled"
            ),
            SysfsCheck(
                path=f"{SYSFS_BASE}/defrag", expected=["madvise", "[madvise]"], name="defrag"
            ),
        ]
    )
    result = analyzer.analyze_data(sample_data, args)
    assert result.status == ExecutionStatus.OK
    assert "as expected" in result.message


def test_analyzer_check_mismatch(analyzer, sample_data):
    """One check expects wrong value -> ERROR; message enumerates path and expected/actual."""
    args = SysSettingsAnalyzerArgs(
        checks=[
            SysfsCheck(path=f"{SYSFS_BASE}/enabled", expected=["never"], name="enabled"),
        ]
    )
    result = analyzer.analyze_data(sample_data, args)
    assert result.status == ExecutionStatus.ERROR
    assert "mismatch" in result.message.lower()
    assert "enabled" in result.message
    assert "never" in result.message
    assert "always" in result.message


def test_analyzer_unknown_path(analyzer, sample_data):
    """Check for path not collected by plugin -> ERROR."""
    args = SysSettingsAnalyzerArgs(
        checks=[
            SysfsCheck(path="/sys/unknown/path", expected=["x"], name="unknown"),
        ]
    )
    result = analyzer.analyze_data(sample_data, args)
    assert result.status == ExecutionStatus.ERROR
    assert "mismatch" in result.message.lower()
    assert "unknown" in result.message
