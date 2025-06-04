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
from nodescraper.plugins.inband.process.analyzer_args import ProcessAnalyzerArgs
from nodescraper.plugins.inband.process.process_analyzer import ProcessAnalyzer
from nodescraper.plugins.inband.process.processdata import ProcessDataModel


@pytest.fixture
def model_obj():
    return ProcessDataModel(
        kfd_process=0,
        cpu_usage=10,
        processes=[
            ("top", "10.0"),
            ("systemd", "0.0"),
            ("kthreadd", "0.0"),
            ("rcu_gp", "0.0"),
            ("rcu_par_gp", "0.0"),
        ],
    )


@pytest.fixture
def config():
    return {"max_kfd_processes": 0, "max_cpu_usage": 40}


@pytest.fixture
def analyzer(system_info):
    return ProcessAnalyzer(system_info=system_info)


def test_nominal_with_config(analyzer, model_obj, config):
    args = ProcessAnalyzerArgs(
        max_kfd_processes=config["max_kfd_processes"], max_cpu_usage=config["max_cpu_usage"]
    )
    result = analyzer.analyze_data(model_obj, args)
    assert result.status == ExecutionStatus.OK
    assert len(result.events) == 0


def test_nominal_no_config(analyzer, model_obj):
    result = analyzer.analyze_data(model_obj)
    assert result.status == ExecutionStatus.OK
    assert len(result.events) == 0


def test_error_kfd_process(analyzer, model_obj, config):
    modified_model_obj = copy.deepcopy(model_obj)
    modified_model_obj.kfd_process = 1
    args = ProcessAnalyzerArgs(
        max_kfd_processes=config["max_kfd_processes"], max_cpu_usage=config["max_cpu_usage"]
    )
    result = analyzer.analyze_data(modified_model_obj, args)

    assert result.status == ExecutionStatus.ERROR
    for event in result.events:
        assert event.category == EventCategory.OS.value
        assert event.priority == EventPriority.CRITICAL


def test_error_cpu_usage(analyzer, model_obj, config):
    modified_model_obj = copy.deepcopy(model_obj)
    args = ProcessAnalyzerArgs(max_kfd_processes=config["max_kfd_processes"], max_cpu_usage=5)
    result = analyzer.analyze_data(modified_model_obj, args)

    assert result.status == ExecutionStatus.ERROR
    for event in result.events:
        assert event.category == EventCategory.OS.value
        assert event.priority == EventPriority.CRITICAL
