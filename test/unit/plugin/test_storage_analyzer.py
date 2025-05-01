import pytest

from errorscraper.enums.eventcategory import EventCategory
from errorscraper.enums.eventpriority import EventPriority
from errorscraper.enums.executionstatus import ExecutionStatus
from errorscraper.models.systeminfo import OSFamily
from errorscraper.plugins.inband.storage.analyzer_args import StorageAnalyzerArgs
from errorscraper.plugins.inband.storage.storage_analyzer import StorageAnalyzer
from errorscraper.plugins.inband.storage.storagedata import (
    DeviceStorageData,
    StorageDataModel,
)


@pytest.fixture
def model_obj():
    return StorageDataModel(
        storage_data={
            "/dev/nvme0n1p2": DeviceStorageData(
                total=943441641472,
                free=869796294656,
                used=25645850624,
                percent=3,
            )
        }
    )


@pytest.fixture
def analyzer(system_info):
    return StorageAnalyzer(system_info=system_info)


def test_nominal_with_config(analyzer, model_obj):
    args = StorageAnalyzerArgs(min_required_free_space="600G")
    result = analyzer.analyze_data(model_obj, args)
    assert result.status == ExecutionStatus.OK
    assert result.message == "'/dev/nvme0n1p2' has 869.8GB available, 3.0% used"
    assert len(result.events) == 0


def test_nominal_no_config(analyzer, model_obj):
    result = analyzer.analyze_data(model_obj)
    assert result.status == ExecutionStatus.OK
    assert result.message == "'/dev/nvme0n1p2' has 869.8GB available, 3.0% used"
    assert len(result.events) == 0


def test_insufficient_free_storage(analyzer, model_obj):
    args = StorageAnalyzerArgs(min_required_free_space="1TB")
    result = analyzer.analyze_data(model_obj, args)
    assert result.status == ExecutionStatus.ERROR
    for event in result.events:
        assert event.category == EventCategory.STORAGE.value
        assert event.priority == EventPriority.CRITICAL


def test_windows_nominal(system_info):
    system_info.os_family = OSFamily.WINDOWS
    analyzer = StorageAnalyzer(system_info=system_info)

    model = StorageDataModel(
        storage_data={
            "C:": DeviceStorageData(
                total=1013310287872,
                free=466435543040,
                used=546874744832,
                percent=53.97,
            )
        }
    )
    args = StorageAnalyzerArgs(min_required_free_space="10GB")

    result = analyzer.analyze_data(model, args)
    assert result.status == ExecutionStatus.OK
    assert result.message == "'C:' has 466.44GB available, 53.97% used"
    assert len(result.events) == 0
