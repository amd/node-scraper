from unittest.mock import MagicMock

import pytest

from errorscraper.enums.eventcategory import EventCategory
from errorscraper.enums.executionstatus import ExecutionStatus
from errorscraper.enums.systeminteraction import SystemInteractionLevel
from errorscraper.models.systeminfo import OSFamily
from errorscraper.plugins.inband.bios.bios_collector import BiosCollector
from errorscraper.plugins.inband.bios.biosdata import BiosDataModel


@pytest.fixture
def bios_collector(system_info, conn_mock):
    return BiosCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.SURFACE,
        connection=conn_mock,
    )


def test_task_body_windows(system_info, bios_collector):
    """Test the _task_body method on Windows."""
    system_info.os_family = OSFamily.WINDOWS

    bios_collector._run_sut_cmd = MagicMock(
        return_value=MagicMock(
            exit_code=0,
            stdout="\n\nSMBIOSBIOSVersion=R23ET70W (1.40 )\n\n\n\n",
        )
    )

    exp_data = BiosDataModel(bios_version="R23ET70W (1.40 )")

    # bios_collector._log_event = MagicMock()
    res, data = bios_collector.collect_data()
    assert data == exp_data


def test_task_body_linux(system_info, bios_collector):
    """Test the _task_body method on Linux."""
    system_info.os_family = OSFamily.LINUX

    bios_collector._run_sut_cmd = MagicMock(
        return_value=MagicMock(
            exit_code=0,
            stdout="2.0.1",
        )
    )

    exp_data = BiosDataModel(bios_version="2.0.1")

    # bios_collector._log_event = MagicMock()
    res, data = bios_collector.collect_data()
    assert data == exp_data


def test_task_body_error(system_info, bios_collector):
    """Test the _task_body method when an error occurs."""
    system_info.os_family = OSFamily.LINUX

    bios_collector._run_sut_cmd = MagicMock(
        return_value=MagicMock(
            exit_code=1,
            command="sh -c 'dmidecode -s bios-version'",
        )
    )

    res, data = bios_collector.collect_data()
    assert res.status == ExecutionStatus.ERROR  # or another appropriate status constant
    assert data is None
    assert res.events[0].category == EventCategory.OS.value
    assert res.events[0].description == "Error checking BIOS version"
