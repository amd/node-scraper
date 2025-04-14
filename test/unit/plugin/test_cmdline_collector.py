from unittest.mock import MagicMock

import pytest

from errorscraper.enums.eventpriority import EventPriority
from errorscraper.enums.executionstatus import ExecutionStatus
from errorscraper.enums.systeminteraction import SystemInteractionLevel
from errorscraper.interfaces.task import SystemCompatibilityError
from errorscraper.models.systeminfo import OSFamily, SystemInfo
from errorscraper.plugins.inband.cmdline.cmdline_collector import CmdlineCollector
from errorscraper.plugins.inband.cmdline.cmdlinedata import CmdlineDataModel


@pytest.fixture
def system_info():
    return SystemInfo(
        name="test_host",
        platform="platform_id",
        os_family=OSFamily.LINUX,
    )


@pytest.fixture
def conn_mock():
    return MagicMock()


@pytest.fixture
def collector(system_info, conn_mock):
    return CmdlineCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.SURFACE,
        connection=conn_mock,
    )


def test_run_linux(collector):
    collector._run_sut_cmd = MagicMock(return_value=MagicMock(exit_code=0, stdout="cmdline output"))
    collector._log_event = MagicMock()

    res, data = collector.collect_data()

    assert res.status == ExecutionStatus.OK
    assert data == CmdlineDataModel(cmdline="cmdline output")
    collector._run_sut_cmd.assert_called_once_with("cat /proc/cmdline")
    collector._log_event.assert_called_once_with(
        category="CMDLINE_READ",
        description="cmdline read",
        data={"cmdline": "cmdline output"},
        priority=EventPriority.INFO,
    )


def test_run_windows(system_info, conn_mock):
    system_info.os_family = OSFamily.WINDOWS

    with pytest.raises(SystemCompatibilityError) as e:
        CmdlineCollector(
            system_info=system_info,
            system_interaction_level=SystemInteractionLevel.SURFACE,
            connection=conn_mock,
        )
    assert str(e.value) == "WINDOWS OS family is not supported"


def test_run_linux_command_error(collector):
    collector._run_sut_cmd = MagicMock(
        return_value=MagicMock(exit_code=1, command="cat /proc/cmdline")
    )

    res, data = collector.collect_data()

    assert res.status == ExecutionStatus.ERROR
    assert data is None
    assert len(res.events) == 1
