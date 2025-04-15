from unittest.mock import MagicMock

import pytest

from errorscraper.enums.eventcategory import EventCategory
from errorscraper.enums.executionstatus import ExecutionStatus
from errorscraper.enums.systeminteraction import SystemInteractionLevel
from errorscraper.models.systeminfo import OSFamily
from errorscraper.plugins.inband.dimm.dimm_collector import DimmCollector
from errorscraper.plugins.inband.dimm.dimmdata import DimmDataModel


@pytest.fixture
def collector(system_info, conn_mock):
    return DimmCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.SURFACE,
        connection=conn_mock,
    )


def test_run_windows(system_info, conn_mock):
    system_info.os_family = OSFamily.WINDOWS
    collector = DimmCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.SURFACE,
        connection=conn_mock,
    )

    collector._run_sut_command = MagicMock(
        return_value=MagicMock(
            exit_code=0,
            stdout="8589934592\n8589934592\n17179869184\n",
        )
    )

    result, data = collector.collect_data()
    assert data == DimmDataModel(dimms="32768.00GB @ 2 x 8192.00GB 1 x 16384.00GB ")


def test_task_body_linux(collector, system_info):
    system_info.os_family = OSFamily.LINUX

    collector._run_sut_command = MagicMock(
        return_value=MagicMock(
            exit_code=0,
            stdout="Size: 64 GB\nSize: 64 GB\nSize: 128 GB\n",
        )
    )

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.OK
    assert data == DimmDataModel(dimms="256GB @ 2 x 64GB1 x 128GB")


def test_task_body_error(collector, system_info):
    system_info.os_family = OSFamily.LINUX

    collector._run_sut_command = MagicMock(
        return_value=MagicMock(
            exit_code=1,
            stderr="Error occurred",
        )
    )

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.ERROR
    assert data is None
    assert result.events[0].category == EventCategory.OS.value
    assert result.events[0].description == "Error checking dimms"
