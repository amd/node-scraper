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
from nodescraper.enums.eventpriority import EventPriority
from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.plugins.inband.kernel.analyzer_args import KernelAnalyzerArgs
from nodescraper.plugins.inband.kernel.kernel_analyzer import KernelAnalyzer
from nodescraper.plugins.inband.kernel.kerneldata import KernelDataModel


@pytest.fixture
def model_obj():
    return KernelDataModel(
        kernel_info="Linux MockSystem 5.13.0-30-generic #1 XYZ Day Month 10 15:19:13 EDT 2024 x86_64 x86_64 x86_64 GNU/Linux",
        kernel_version="5.13.0-30-generic",
    )


@pytest.fixture
def config():
    return {
        "kernel_name": [
            "Linux MockSystem 5.13.0-30-generic #1 XYZ Day Month 10 15:19:13 EDT 2024 x86_64 x86_64 x86_64 GNU/Linux",
            "Linux MockSystem1 5.15.0-31-generic #39 XYZA Day MonthX 10 24:19:13 IST 2024 x86_64 GNU/Linux",
            "Linux MockSystem2 5.18.0-32-generic #178 XYZaB Day MonthY 10 15:06:11 PDT 2024 Linux",
        ],
        "invalid": "invalid",
    }


def test_all_good_data(system_info, model_obj, config):
    args = KernelAnalyzerArgs(exp_kernel=config["kernel_name"])
    analyzer = KernelAnalyzer(system_info)
    result = analyzer.analyze_data(model_obj, args)

    assert result.status == ExecutionStatus.OK
    assert "Kernel matches expected" in result.message
    assert all(event.priority != EventPriority.CRITICAL for event in result.events)


def test_all_good_data_strings(system_info, model_obj, config):
    args = KernelAnalyzerArgs(exp_kernel=config["kernel_name"][0])
    analyzer = KernelAnalyzer(system_info)
    result = analyzer.analyze_data(model_obj, args)

    assert result.status == ExecutionStatus.OK
    assert "Kernel matches expected" in result.message
    assert all(
        event.priority not in [EventPriority.WARNING, EventPriority.ERROR, EventPriority.CRITICAL]
        for event in result.events
    )


def test_no_config_data(system_info, model_obj):
    analyzer = KernelAnalyzer(system_info)
    result = analyzer.analyze_data(model_obj)

    assert result.status == ExecutionStatus.NOT_RAN
    assert len(result.events) == 0


def test_invalid_kernel(system_info, model_obj, config):
    args = KernelAnalyzerArgs(exp_kernel=config["kernel_name"])
    model_obj.kernel_info = "some_invalid"

    analyzer = KernelAnalyzer(system_info)
    result = analyzer.analyze_data(model_obj, args=args)

    assert result.status == ExecutionStatus.ERROR
    assert "Kernel mismatch" in result.message
    assert any(
        event.priority == EventPriority.CRITICAL and event.category == EventCategory.OS.value
        for event in result.events
    )


def test_unexpected_kernel(system_info, model_obj):
    args = KernelAnalyzerArgs(exp_kernel=["5.18.2-mi300-build"])
    analyzer = KernelAnalyzer(system_info)
    result = analyzer.analyze_data(model_obj, args)

    assert result.status == ExecutionStatus.ERROR
    assert "Kernel mismatch!" in result.message
    assert any(
        event.priority == EventPriority.CRITICAL and event.category == EventCategory.OS.value
        for event in result.events
    )


def test_invalid_kernel_config(system_info, model_obj, config):
    args = KernelAnalyzerArgs(exp_kernel=config["invalid"])
    analyzer = KernelAnalyzer(system_info)
    result = analyzer.analyze_data(model_obj, args)

    assert result.status == ExecutionStatus.ERROR


def test_match_regex(system_info, model_obj):
    args = KernelAnalyzerArgs(exp_kernel=[r".*5\.13\.\d+-\d+-[\w-]+.*"], regex_match=True)
    analyzer = KernelAnalyzer(system_info)
    result = analyzer.analyze_data(model_obj, args)
    assert result.status == ExecutionStatus.OK


def test_mismatch_regex(system_info, model_obj):
    args = KernelAnalyzerArgs(exp_kernel=[r".*4\.13\.\d+-\d+-[\w-]+.*"], regex_match=True)
    analyzer = KernelAnalyzer(system_info)
    result = analyzer.analyze_data(model_obj, args)

    assert result.status == ExecutionStatus.ERROR
    assert len(result.events) == 1
    assert result.events[0].priority == EventPriority.CRITICAL
    assert result.events[0].category == EventCategory.OS.value
    assert "Kernel mismatch!" in result.events[0].description


def test_bad_regex(system_info, model_obj):
    args = KernelAnalyzerArgs(exp_kernel=[r"4.[3.\d-\d+-[\w]+"], regex_match=True)
    analyzer = KernelAnalyzer(system_info)
    result = analyzer.analyze_data(model_obj, args)

    assert result.status == ExecutionStatus.ERROR
    assert len(result.events) == 2
    assert result.events[0].priority == EventPriority.ERROR
    assert result.events[0].category == EventCategory.RUNTIME.value
    assert result.events[0].description == "Kernel regex is invalid"
    assert result.events[1].priority == EventPriority.CRITICAL
    assert result.events[1].category == EventCategory.OS.value
    assert "Kernel mismatch!" in result.events[1].description
