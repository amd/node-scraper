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
def analyzer(system_info):
    return RocmAnalyzer(system_info=system_info)


@pytest.fixture
def model_obj():
    return RocmDataModel(rocm_version="6.2.0-66", rocm_latest_versioned_path="/opt/rocm-7.1.0")


@pytest.fixture
def config():
    return {
        "rocm_version": ["6.2.0-66"],
        "invalid": "invalid",
        "rocm_latest": "/opt/rocm-7.1.0",
    }


def test_all_good_data(analyzer, model_obj, config):
    args = RocmAnalyzerArgs(exp_rocm=config["rocm_version"], exp_rocm_latest=config["rocm_latest"])
    result = analyzer.analyze_data(model_obj, args)
    assert result.status == ExecutionStatus.OK
    assert "ROCm version matches expected" in result.message
    assert "ROCm latest path validated" in result.message
    assert all(
        event.priority not in {EventPriority.WARNING, EventPriority.ERROR, EventPriority.CRITICAL}
        for event in result.events
    )


def test_no_config_data(analyzer, model_obj):
    result = analyzer.analyze_data(model_obj)
    assert result.status == ExecutionStatus.NOT_RAN


def test_invalid_rocm_version(analyzer, model_obj):
    modified_model = copy.deepcopy(model_obj)
    modified_model.rocm_version = "some_invalid_version"
    args = RocmAnalyzerArgs(exp_rocm=["6.2.0-66"])
    result = analyzer.analyze_data(modified_model, args)
    assert result.status == ExecutionStatus.ERROR
    assert "ROCm version mismatch!" in result.message
    for event in result.events:
        assert event.priority == EventPriority.CRITICAL
        assert event.category == EventCategory.SW_DRIVER.value


def test_unexpected_rocm_version(analyzer, model_obj):
    args = RocmAnalyzerArgs(exp_rocm=["9.8.7-65", "1.2.3-45"])
    result = analyzer.analyze_data(model_obj, args)
    assert result.status == ExecutionStatus.ERROR
    assert "ROCm version mismatch!" in result.message
    for event in result.events:
        assert event.priority == EventPriority.CRITICAL
        assert event.category == EventCategory.SW_DRIVER.value


def test_invalid_user_config(analyzer, model_obj, config):
    result = analyzer.analyze_data(model_obj, None)
    assert result.status == ExecutionStatus.NOT_RAN


def test_rocm_latest_path_mismatch(analyzer, model_obj):
    """Test that rocm_latest path mismatch is detected and logged"""
    args = RocmAnalyzerArgs(exp_rocm=["6.2.0-66"], exp_rocm_latest="/opt/rocm-6.2.0")
    result = analyzer.analyze_data(model_obj, args)
    assert result.status == ExecutionStatus.ERROR
    assert "ROCm latest path mismatch" in result.message
    assert "/opt/rocm-6.2.0" in result.message  # expected
    assert "/opt/rocm-7.1.0" in result.message  # actual
    for event in result.events:
        assert event.priority == EventPriority.CRITICAL
        assert event.category == EventCategory.SW_DRIVER.value
