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

from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.plugins.inband.memory.analyzer_args import MemoryAnalyzerArgs
from nodescraper.plugins.inband.memory.memory_analyzer import MemoryAnalyzer
from nodescraper.plugins.inband.memory.memorydata import MemoryDataModel


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


def test_minimum_system_memory_passes_nominal_2tib(analyzer):
    """2048 GiB nominal still passes when the OS reports slightly less."""
    model = MemoryDataModel(mem_free="1900Gi", mem_total="2016Gi", mem_available="1900Gi")
    result = analyzer.analyze_data(
        model,
        MemoryAnalyzerArgs(minimum_system_memory_gib=2048, ratio=0.9, memory_threshold="4Ti"),
    )
    assert result.status == ExecutionStatus.OK


def test_minimum_system_memory_fails(analyzer):
    """Installed-memory failure still runs the max-usage check and stays an error."""
    model = MemoryDataModel(mem_free="100Gi", mem_total="1024Gi", mem_available="100Gi")
    result = analyzer.analyze_data(
        model,
        MemoryAnalyzerArgs(minimum_system_memory_gib=2048),
    )
    assert result.status == ExecutionStatus.ERROR
    assert "Installed system memory is below the minimum" in result.message
    descriptions = [event.description for event in result.events]
    assert any(description.startswith("Installed memory is") for description in descriptions)
    assert any(description.startswith("Memory usage exceeded") for description in descriptions)


def test_minimum_system_memory_failure_keeps_error_when_later_checks_pass(analyzer):
    """A passing free-memory and max-usage check must not clear the installed-memory error."""
    model = MemoryDataModel(mem_free="1010Gi", mem_total="1024Gi", mem_available="1010Gi")
    result = analyzer.analyze_data(
        model,
        MemoryAnalyzerArgs(
            minimum_system_memory_gib=2048,
            minimum_free_memory_percent=10,
            ratio=0.9,
            memory_threshold="4Ti",
        ),
    )
    assert result.status == ExecutionStatus.ERROR
    assert "Installed system memory is below the minimum" in result.message
    assert "within limit" not in result.message
    assert len(result.events) == 1
    assert result.events[0].description.startswith("Installed memory is")


def test_minimum_system_memory_failure_still_checks_free_percent(analyzer):
    model = MemoryDataModel(mem_free="10Gi", mem_total="1024Gi", mem_available="10Gi")
    result = analyzer.analyze_data(
        model,
        MemoryAnalyzerArgs(
            minimum_system_memory_gib=2048,
            minimum_free_memory_percent=50,
            ratio=0.999,
            memory_threshold="4Ti",
        ),
    )
    assert result.status == ExecutionStatus.ERROR
    assert "Installed system memory is below the minimum" in result.message
    descriptions = [event.description for event in result.events]
    assert any(description.startswith("Installed memory is") for description in descriptions)
    assert any(description.startswith("Available memory is") for description in descriptions)
    assert not any(description.startswith("Memory usage exceeded") for description in descriptions)


def test_config_provided(analyzer, model_obj):
    args = MemoryAnalyzerArgs(ratio=0.66, memory_threshold="30Gi")
    result = analyzer.analyze_data(model_obj, args)
    assert result.status == ExecutionStatus.OK


def test_minimum_free_memory_percent_and_ratio_pass(analyzer):
    model = MemoryDataModel(
        mem_total="100Gi",
        mem_free="20Gi",
        mem_available="20Gi",
    )

    result = analyzer.analyze_data(
        model,
        MemoryAnalyzerArgs(
            minimum_free_memory_percent=10,
            ratio=0.9,
            memory_threshold="100Gi",
        ),
    )

    assert result.status == ExecutionStatus.OK
    assert "20.00%" in result.message
    assert "ratio=0.90" in result.message


def test_minimum_free_memory_percent_passes_ratio_fails(analyzer):
    model = MemoryDataModel(
        mem_total="100Gi",
        mem_free="20Gi",
        mem_available="20Gi",
    )

    result = analyzer.analyze_data(
        model,
        MemoryAnalyzerArgs(
            minimum_free_memory_percent=10,
            ratio=0.5,
            memory_threshold="100Gi",
        ),
    )

    assert result.status == ExecutionStatus.ERROR
    assert "Memory usage exceeded max allowed!" in result.message


def test_ratio_passes_minimum_free_memory_percent_fails(analyzer):
    model = MemoryDataModel(
        mem_total="100Gi",
        mem_free="90Gi",
        mem_available="90Gi",
    )

    result = analyzer.analyze_data(
        model,
        MemoryAnalyzerArgs(
            minimum_free_memory_percent=95,
            ratio=0.5,
            memory_threshold="100Gi",
        ),
    )

    assert result.status == ExecutionStatus.ERROR
    assert "Minimum free memory percentage not met" in result.message
    assert len(result.events) == 1


def test_minimum_free_memory_percent_fails(analyzer):
    model = MemoryDataModel(
        mem_total="100Gi",
        mem_free="5Gi",
        mem_available="5Gi",
    )

    result = analyzer.analyze_data(
        model,
        MemoryAnalyzerArgs(minimum_free_memory_percent=10),
    )

    assert result.status == ExecutionStatus.ERROR
    assert len(result.events) == 1
    assert result.events[0].data["available_percent"] == pytest.approx(5.0)


def test_linux_low_free_high_available_passes(analyzer):
    """MemFree alone looks tight; MemAvailable reflects reclaimable cache."""
    model = MemoryDataModel(
        mem_total="128Gi",
        mem_free="2Gi",
        mem_available="100Gi",
    )
    args = MemoryAnalyzerArgs(memory_threshold="128Gi", ratio=0.66)
    result = analyzer.analyze_data(model, args)
    assert result.status == ExecutionStatus.OK


def test_linux_low_free_high_available_fails_without_mem_available(analyzer):
    model = MemoryDataModel(
        mem_total="128Gi",
        mem_free="2Gi",
    )
    args = MemoryAnalyzerArgs(memory_threshold="128Gi", ratio=0.66)
    result = analyzer.analyze_data(model, args)
    assert result.status == ExecutionStatus.ERROR


def test_windows_like_memory(analyzer):
    model = MemoryDataModel(mem_free="751720910848", mem_total="1013310287872")
    result = analyzer.analyze_data(model)
    assert result.status == ExecutionStatus.ERROR
    assert "Memory usage exceeded max allowed!" in result.message
