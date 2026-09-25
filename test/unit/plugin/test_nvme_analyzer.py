###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
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
