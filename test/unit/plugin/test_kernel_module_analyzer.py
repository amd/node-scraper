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

from nodescraper.enums.eventcategory import EventCategory
from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.models.systeminfo import OSFamily
from nodescraper.plugins.inband.kernel_module.analyzer_args import (
    KernelModuleAnalyzerArgs,
)
from nodescraper.plugins.inband.kernel_module.kernel_module_analyzer import (
    KernelModuleAnalyzer,
)
from nodescraper.plugins.inband.kernel_module.kernel_module_data import (
    KernelModuleDataModel,
)


@pytest.fixture
def sample_modules():
    return {
        "modA": {"parameters": {"p": 1}},
        "otherMod": {"parameters": {"p": 2}},
        "TESTmod": {"parameters": {"p": 3}},
        "amdABC": {"parameters": {"p": 3}},
    }


@pytest.fixture
def data_model(sample_modules):
    return KernelModuleDataModel(kernel_modules=sample_modules)


@pytest.fixture
def analyzer(system_info):
    system_info.os_family = OSFamily.LINUX
    return KernelModuleAnalyzer(system_info=system_info)


def test_filter_modules_by_pattern_none(sample_modules, analyzer):
    matched, unmatched = analyzer.filter_modules_by_pattern(sample_modules, None)
    assert matched == sample_modules
    assert unmatched == []


def test_filter_modules_by_pattern_strict(sample_modules, analyzer):
    matched, unmatched = analyzer.filter_modules_by_pattern(sample_modules, [r"mod$"])
    assert set(matched) == {"otherMod", "TESTmod"}
    assert unmatched == []


def test_filter_modules_by_pattern_unmatched(sample_modules, analyzer):
    matched, unmatched = analyzer.filter_modules_by_pattern(sample_modules, ["foo"])
    assert matched == {}
    assert unmatched == ["foo"]


def test_filter_name_and_param_all_match(sample_modules, analyzer):
    to_match = {"modA": {"parameters": {"p": 1}}}
    matched, unmatched = analyzer.filter_modules_by_name_and_param(sample_modules, to_match)
    assert matched == {"modA": sample_modules["modA"]}
    assert unmatched == {}


def test_filter_name_and_param_param_mismatch(sample_modules, analyzer):
    to_match = {"modA": {"parameters": {"p": 999}}}
    matched, unmatched = analyzer.filter_modules_by_name_and_param(sample_modules, to_match)
    assert matched == {}
    assert "modA" in unmatched
    assert "p" in unmatched["modA"]["parameters"]


def test_filter_name_and_param_missing_module(sample_modules, analyzer):
    to_match = {"bogus": {"parameters": {"x": 1}}}
    matched, unmatched = analyzer.filter_modules_by_name_and_param(sample_modules, to_match)
    assert matched == {}
    assert "bogus" in unmatched


def test_analyze_data_default(data_model, analyzer):
    result = analyzer.analyze_data(data_model, None)
    assert result.status == ExecutionStatus.OK


def test_analyze_data_regex_success(data_model, analyzer):
    args = KernelModuleAnalyzerArgs(regex_filter=["^TESTmod$"])
    result = analyzer.analyze_data(data_model, args)
    assert result.status == ExecutionStatus.OK
    ev = result.events[0]
    assert ev.description == "KernelModules analyzed"
    fm = ev.data["filtered_modules"]
    assert set(fm) == {"TESTmod"}


def test_analyze_data_regex_invalid_pattern(data_model, analyzer):
    args = KernelModuleAnalyzerArgs(regex_filter=["*invalid"])
    result = analyzer.analyze_data(data_model, args)
    assert result.status in (ExecutionStatus.ERROR, ExecutionStatus.EXECUTION_FAILURE)
    assert any(EventCategory.RUNTIME.value in ev.category for ev in result.events)


def test_analyze_data_regex_unmatched_patterns(data_model, analyzer):
    args = KernelModuleAnalyzerArgs(regex_filter=["modA", "nope"])
    result = analyzer.analyze_data(data_model, args)
    assert result.status == ExecutionStatus.ERROR
    assert any(
        ev.description.startswith("KernelModules did not match all patterns")
        for ev in result.events
    )


def test_analyze_data_name_only_success(data_model, analyzer):
    args = KernelModuleAnalyzerArgs(kernel_modules={"modA": {"parameters": {"p": 1}}})
    result = analyzer.analyze_data(data_model, args)
    assert result.status == ExecutionStatus.OK
    assert result.message == "task completed successfully"


def test_no_analyzer_args(data_model, analyzer):
    args = KernelModuleAnalyzerArgs(kernel_modules={}, regex_filter=[])
    result = analyzer.analyze_data(data_model, args)
    assert result.status == ExecutionStatus.NOT_RAN
    assert (
        result.message == "No values provided in analysis args for: kernel_modules and regex_match"
    )
