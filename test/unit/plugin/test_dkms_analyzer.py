###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
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

from nodescraper.enums.eventpriority import EventPriority
from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.plugins.inband.dkms.analyzer_args import DkmsAnalyzerArgs
from nodescraper.plugins.inband.dkms.dkms_analyzer import DkmsAnalyzer
from nodescraper.plugins.inband.dkms.dkmsdata import DkmsDataModel


@pytest.fixture
def model_obj():
    return DkmsDataModel(
        status="amdgpu/6.8.5-2009582.22.04, 5.15.0-91-generic, x86_64: installed",
        version="dkms-2.8.7",
    )


@pytest.fixture
def config():
    return {
        "status": [
            "amdgpu/6.8.5-2009582.22.04, 5.15.0-91-generic, x86_64: installed",
            "amdgpu/6.8.5-2009582.22.04, 5.15.0-117-generic, x86_64: installed\n",
        ],
        "regex_status": r"amdgpu/\d+\.\d+\.\d+-\d+\.\d+\.\d+, \d+\.\d+\.\d+-\w+-generic, x86_64: installed",
        "regex_version": [r"dkms-\d.\d.\d"],
        "version": ["dkms-2.8.7"],
        "invalid": "invalid",
        "invalid_regex": r"\d(",
        "regex_status_no_match": "ddd",
        "regex_version_no_match": "ddd",
    }


def test_all_good_data(system_info, model_obj, config):
    analyzer = DkmsAnalyzer(system_info=system_info)
    args = DkmsAnalyzerArgs(dkms_status=config["status"], dkms_version=config["version"])
    result = analyzer.analyze_data(data=model_obj, args=args)

    assert result.status == ExecutionStatus.OK
    assert result.message == "task completed successfully"
    assert all(
        event.priority not in [EventPriority.WARNING, EventPriority.ERROR, EventPriority.CRITICAL]
        for event in result.events
    )


def test_all_good_data_strings(system_info, model_obj, config):
    analyzer = DkmsAnalyzer(system_info=system_info)
    args = DkmsAnalyzerArgs(dkms_status=config["status"][0], dkms_version=config["version"])
    result = analyzer.analyze_data(data=model_obj, args=args)

    assert result.status == ExecutionStatus.OK
    assert result.message == "task completed successfully"
    assert all(
        event.priority not in [EventPriority.WARNING, EventPriority.ERROR, EventPriority.CRITICAL]
        for event in result.events
    )


def test_missing_data(system_info, model_obj, config):
    analyzer = DkmsAnalyzer(system_info=system_info)
    args = DkmsAnalyzerArgs(dkms_status=config["status"])  # dkms_version omitted
    result = analyzer.analyze_data(data=model_obj, args=args)

    assert result.status == ExecutionStatus.ERROR
    assert result.events[0].description == "DKMS version has an unexpected value"
    assert len(result.events) == 1


def test_invalid_data(system_info, model_obj, config):
    analyzer = DkmsAnalyzer(system_info=system_info)
    args = DkmsAnalyzerArgs(dkms_status=config["status"], dkms_version=config["invalid"])
    result = analyzer.analyze_data(data=model_obj, args=args)

    assert result.status == ExecutionStatus.ERROR
    assert result.events[0].description == "DKMS version has an unexpected value"
    assert len(result.events) == 1


def test_wrong_dkms_version(system_info, model_obj, config):
    analyzer = DkmsAnalyzer(system_info=system_info)
    args = DkmsAnalyzerArgs(dkms_status=config["status"], dkms_version=["wrong string"])
    result = analyzer.analyze_data(data=model_obj, args=args)

    assert result.status == ExecutionStatus.ERROR
    assert "DKMS data mismatch" in result.message


def test_wrong_dkms_status(system_info, model_obj, config):
    analyzer = DkmsAnalyzer(system_info=system_info)
    args = DkmsAnalyzerArgs(dkms_status=["wrong string"], dkms_version=config["version"])
    result = analyzer.analyze_data(data=model_obj, args=args)

    assert result.status == ExecutionStatus.ERROR
    assert "DKMS data mismatch" in result.message


def test_wrong_dkms_status_and_version(system_info, model_obj):
    analyzer = DkmsAnalyzer(system_info=system_info)
    args = DkmsAnalyzerArgs(dkms_status=["wrong string"], dkms_version=["wrong string"])
    result = analyzer.analyze_data(data=model_obj, args=args)

    assert result.status == ExecutionStatus.ERROR
    assert "DKMS data mismatch" in result.message


def test_regex_mismatch(system_info, model_obj, config):
    analyzer = DkmsAnalyzer(system_info=system_info)
    args = DkmsAnalyzerArgs(
        dkms_status=config["regex_status_no_match"],
        dkms_version=config["regex_version_no_match"],
        regex_match=True,
    )
    result = analyzer.analyze_data(data=model_obj, args=args)

    assert result.status == ExecutionStatus.ERROR
    assert len(result.events) == 2
    assert result.events[0].description == "DKMS status has an unexpected value"


def test_regex_matches(system_info, model_obj, config):
    analyzer = DkmsAnalyzer(system_info=system_info)
    args = DkmsAnalyzerArgs(
        dkms_status=config["regex_status"],
        dkms_version=config["regex_version"],
        regex_match=True,
    )
    result = analyzer.analyze_data(data=model_obj, args=args)

    assert result.status == ExecutionStatus.OK
    assert len(result.events) == 0


def test_invalid_regex_mismatch(system_info, model_obj, config):
    analyzer = DkmsAnalyzer(system_info=system_info)
    args = DkmsAnalyzerArgs(
        dkms_status=config["regex_status"],
        dkms_version=config["invalid_regex"],
        regex_match=True,
    )
    result = analyzer.analyze_data(data=model_obj, args=args)

    assert result.status == ExecutionStatus.ERROR
    assert len(result.events) == 2
    assert result.events[0].description == "DKMS version regex is invalid"
