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
from nodescraper.plugins.ooband.redfish_oem_diag import (
    RedfishOemDiagAnalyzer,
    RedfishOemDiagAnalyzerArgs,
    RedfishOemDiagDataModel,
)
from nodescraper.plugins.ooband.redfish_oem_diag.oem_diag_data import OemDiagTypeResult


@pytest.fixture
def redfish_oem_diag_analyzer(system_info):
    return RedfishOemDiagAnalyzer(system_info=system_info)


def test_redfish_oem_diag_analyzer_no_results(redfish_oem_diag_analyzer):
    data = RedfishOemDiagDataModel(results={})
    result = redfish_oem_diag_analyzer.analyze_data(data)
    assert result.status == ExecutionStatus.NOT_RAN
    assert result.message == "No OEM diagnostic results to analyze"


def test_redfish_oem_diag_analyzer_all_success(redfish_oem_diag_analyzer):
    data = RedfishOemDiagDataModel(
        results={
            "JournalControl": OemDiagTypeResult(success=True, error=None, metadata={}),
            "AllLogs": OemDiagTypeResult(success=True, error=None, metadata={}),
        }
    )
    result = redfish_oem_diag_analyzer.analyze_data(data)
    assert result.status == ExecutionStatus.OK
    assert "2/2 types collected" in result.message


def test_redfish_oem_diag_analyzer_some_failed_without_require_all(redfish_oem_diag_analyzer):
    data = RedfishOemDiagDataModel(
        results={
            "JournalControl": OemDiagTypeResult(success=True, error=None, metadata={}),
            "AllLogs": OemDiagTypeResult(success=False, error="Timeout", metadata=None),
        }
    )
    result = redfish_oem_diag_analyzer.analyze_data(data)
    assert result.status == ExecutionStatus.OK
    assert "1/2 types collected" in result.message


def test_redfish_oem_diag_analyzer_some_failed_with_require_all_success(redfish_oem_diag_analyzer):
    data = RedfishOemDiagDataModel(
        results={
            "JournalControl": OemDiagTypeResult(success=True, error=None, metadata={}),
            "AllLogs": OemDiagTypeResult(success=False, error="Task timeout", metadata=None),
        }
    )
    args = RedfishOemDiagAnalyzerArgs(require_all_success=True)
    result = redfish_oem_diag_analyzer.analyze_data(data, args=args)
    assert result.status == ExecutionStatus.ERROR
    assert "1 type(s) failed" in result.message
    assert "AllLogs" in result.message
    assert len(result.events) >= 1
    assert any(
        "AllLogs" in (e.description or "") or "failed" in (e.description or "").lower()
        for e in result.events
    )


def test_redfish_oem_diag_analyzer_all_failed_require_all_success(redfish_oem_diag_analyzer):
    data = RedfishOemDiagDataModel(
        results={
            "JournalControl": OemDiagTypeResult(success=False, error="Err1", metadata=None),
            "AllLogs": OemDiagTypeResult(success=False, error="Err2", metadata=None),
        }
    )
    args = RedfishOemDiagAnalyzerArgs(require_all_success=True)
    result = redfish_oem_diag_analyzer.analyze_data(data, args=args)
    assert result.status == ExecutionStatus.ERROR
    assert "2 type(s) failed" in result.message


def test_redfish_oem_diag_analyzer_require_all_success_all_ok(redfish_oem_diag_analyzer):
    data = RedfishOemDiagDataModel(
        results={
            "JournalControl": OemDiagTypeResult(success=True, error=None, metadata={}),
        }
    )
    args = RedfishOemDiagAnalyzerArgs(require_all_success=True)
    result = redfish_oem_diag_analyzer.analyze_data(data, args=args)
    assert result.status == ExecutionStatus.OK
    assert "1/1 types collected" in result.message
