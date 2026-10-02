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
from nodescraper.enums import EventPriority, ExecutionStatus
from nodescraper.plugins.inband.nvme.analyzer_args import NvmeAnalyzerArgs
from nodescraper.plugins.inband.nvme.nvme_analyzer import NvmeAnalyzer
from nodescraper.plugins.inband.nvme.nvmedata import DeviceNvmeData, NvmeDataModel


def test_nvme_smart_media_errors_within_threshold(system_info):
    analyzer = NvmeAnalyzer(system_info)
    data = NvmeDataModel(
        devices={
            "nvme0": DeviceNvmeData(smart_log="media_errors : 0"),
        }
    )

    result = analyzer.analyze_data(data, NvmeAnalyzerArgs(maximum_smart_error_count=0))

    assert result.status == ExecutionStatus.OK
    assert not result.events


def test_nvme_smart_media_errors_exceed_threshold(system_info):
    analyzer = NvmeAnalyzer(system_info)
    data = NvmeDataModel(
        devices={
            "nvme0": DeviceNvmeData(smart_log="media_errors : 2"),
        }
    )

    result = analyzer.analyze_data(data, NvmeAnalyzerArgs(maximum_smart_error_count=0))

    assert result.status == ExecutionStatus.ERROR
    assert len(result.events) == 1
    assert result.events[0].priority == EventPriority.ERROR
    assert result.events[0].data["media_errors"] == 2


def test_nvme_smart_media_errors_missing_logs_warning(system_info):
    analyzer = NvmeAnalyzer(system_info)
    data = NvmeDataModel(
        devices={
            "nvme0": DeviceNvmeData(smart_log="critical_warning : 0"),
        }
    )

    result = analyzer.analyze_data(data, NvmeAnalyzerArgs(maximum_smart_error_count=0))

    assert result.status == ExecutionStatus.OK
    assert len(result.events) == 1
    assert result.events[0].priority == EventPriority.WARNING


def test_nvme_smart_check_not_run_without_threshold(system_info):
    analyzer = NvmeAnalyzer(system_info)
    data = NvmeDataModel(
        devices={
            "nvme0": DeviceNvmeData(smart_log="media_errors : 2"),
        }
    )

    result = analyzer.analyze_data(data, NvmeAnalyzerArgs())

    assert result.status == ExecutionStatus.NOT_RAN
