from unittest.mock import MagicMock

import pytest

from errorscraper.enums.executionstatus import ExecutionStatus
from errorscraper.enums.systeminteraction import SystemInteractionLevel
from errorscraper.interfaces.task import SystemCompatibilityError
from errorscraper.models.systeminfo import OSFamily
from errorscraper.plugins.inband.process.process_collector import ProcessCollector
from errorscraper.plugins.inband.process.processdata import ProcessDataModel


@pytest.fixture
def collector(system_info, conn_mock):
    return ProcessCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


def test_run_linux(collector, conn_mock):
    collector.system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.side_effect = [
        MagicMock(
            exit_code=0,
            stdout="PID PROCESS NAME GPU(s) VRAM USED SDMA USED CU OCCUPANCY\n8246 TransferBench 8 2267283456 0 0",
            stderr="",
        ),
        MagicMock(
            exit_code=0,
            stdout="%Cpu(s):  0.1 us,  0.1 sy,  0.0 ni, 90.0 id",
            stderr="",
        ),
        MagicMock(
            exit_code=0,
            stdout="356817 user 20 0 32112 14196 10556 R 10.0 0.0 0:00.07 top\n"
            "1 root 20 0 166596 11916 8316 S 0.0 0.0 1:32.14 systemd",
            stderr="",
        ),
    ]

    result, data = collector.collect_data()
    assert result.status == ExecutionStatus.OK
    assert data == ProcessDataModel(
        kfd_process=1,
        cpu_usage=10,
        processes=[
            ("top", "10.0"),
            ("systemd", "0.0"),
        ],
    )


def test_unsupported_platform(system_info, conn_mock):
    system_info.os_family = OSFamily.WINDOWS
    with pytest.raises(SystemCompatibilityError):
        ProcessCollector(
            system_info=system_info,
            system_interaction_level=SystemInteractionLevel.PASSIVE,
            connection=conn_mock,
        )


def test_exit_failure(collector, conn_mock):
    collector.system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.side_effect = [
        MagicMock(exit_code=1, stdout="", stderr=""),
        MagicMock(exit_code=0, stdout="", stderr=""),
        MagicMock(exit_code=0, stdout="", stderr=""),
    ]

    result, data = collector.collect_data()
    assert result.status == ExecutionStatus.EXECUTION_FAILURE
    assert data is None
