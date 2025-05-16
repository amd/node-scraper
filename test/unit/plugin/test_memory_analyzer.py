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

from errorscraper.enums.executionstatus import ExecutionStatus
from errorscraper.plugins.inband.memory.analyzer_args import MemoryAnalyzerArgs
from errorscraper.plugins.inband.memory.memory_analyzer import MemoryAnalyzer
from errorscraper.plugins.inband.memory.memorydata import MemoryDataModel


@pytest.fixture
def model_obj():
    return MemoryDataModel(mem_free="2160459761152", mem_total="2164113772544")


@pytest.fixture
def analyzer(system_info, model_obj):
    return MemoryAnalyzer(system_info=system_info, data_model=model_obj)


def test_normal_memory_usage(analyzer, model_obj):
    result = analyzer.analyze_data(model_obj)
    assert result.status == ExecutionStatus.OK


def test_too_much_memory_usage(analyzer, model_obj):
    model_obj.mem_free = "90Gi"
    model_obj.mem_total = "128Gi"

    result = analyzer.analyze_data(model_obj)
    assert result.status == ExecutionStatus.ERROR


def test_config_provided(analyzer, model_obj):
    args = MemoryAnalyzerArgs(ratio=0.66, memory_threshold="30Gi")
    result = analyzer.analyze_data(model_obj, args)
    assert result.status == ExecutionStatus.OK


def test_windows_like_memory(analyzer):
    model = MemoryDataModel(mem_free="751720910848", mem_total="1013310287872")
    result = analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.ERROR
    assert "Memory usage is more than the maximum allowed used memory!" in result.message
