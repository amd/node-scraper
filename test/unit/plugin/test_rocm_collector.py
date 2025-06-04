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
import copy

import pytest

from nodescraper.enums.eventcategory import EventCategory
from nodescraper.enums.eventpriority import EventPriority
from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.plugins.inband.rocm.analyzer_args import RocmAnalyzerArgs
from nodescraper.plugins.inband.rocm.rocm_analyzer import RocmAnalyzer
from nodescraper.plugins.inband.rocm.rocmdata import RocmDataModel


@pytest.fixture
def model_obj():
    return RocmDataModel(rocm_version="6.2.0-66")


@pytest.fixture
def analyzer(system_info):
    return RocmAnalyzer(system_info=system_info)


def test_all_good_data(analyzer, model_obj):
    args = RocmAnalyzerArgs(exp_rocm=["6.2.0-66"])
    result = analyzer.analyze_data(model_obj, args=args)
    assert result.status == ExecutionStatus.OK
    assert result.message == "ROCm version matches expected"
    assert all(
        event.priority not in [EventPriority.WARNING, EventPriority.ERROR, EventPriority.CRITICAL]
        for event in result.events
    )


def test_no_config_data(analyzer, model_obj):
    result = analyzer.analyze_data(model_obj)
    assert result.status == ExecutionStatus.NOT_RAN


def test_invalid_rocm_version(analyzer, model_obj):
    modified_model = copy.deepcopy(model_obj)
    modified_model.rocm_version = "some_invalid_version"
    args = RocmAnalyzerArgs(exp_rocm=["6.2.0-66"])
    result = analyzer.analyze_data(modified_model, args=args)

    assert result.status == ExecutionStatus.ERROR
    assert result.message == "ROCm version mismatch! (1 errors)"
    for event in result.events:
        assert event.priority == EventPriority.CRITICAL
        assert event.category == EventCategory.SW_DRIVER.value


def test_unexpected_rocm_version(analyzer, model_obj):
    args = RocmAnalyzerArgs(exp_rocm=["9.8.7-65", "1.2.3-45"])
    result = analyzer.analyze_data(model_obj, args=args)

    assert result.status == ExecutionStatus.ERROR
    assert "ROCm version mismatch! (1 errors)" in result.message
    for event in result.events:
        assert event.priority == EventPriority.CRITICAL
        assert event.category == EventCategory.SW_DRIVER.value


def test_invalid_user_config(analyzer, model_obj):
    result = analyzer.analyze_data(model_obj, None)
    assert result.status == ExecutionStatus.NOT_RAN
