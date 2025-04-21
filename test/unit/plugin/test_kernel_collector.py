import pytest

from errorscraper.connection.inband.inband import CommandArtifact
from errorscraper.enums.executionstatus import ExecutionStatus
from errorscraper.enums.systeminteraction import SystemInteractionLevel
from errorscraper.models.systeminfo import OSFamily
from errorscraper.plugins.inband.kernel.kernel_collector import KernelCollector
from errorscraper.plugins.inband.kernel.kerneldata import KernelDataModel


@pytest.fixture
def collector(system_info, conn_mock):
    return KernelCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


def test_run_windows(collector, conn_mock):
    collector.system_info.os_family = OSFamily.WINDOWS
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=0,
        stdout="Version=10.0.19041.1237",
        stderr="",
        command="wmic os get Version /Value",
    )

    result, data = collector.collect_data()

    assert data == KernelDataModel(kernel_version="10.0.19041.1237")
    assert result.status == ExecutionStatus.OK


def test_run_linux(collector, conn_mock):
    collector.system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=0,
        stdout="5.4.0-88-generic",
        stderr="",
        command="sh -c 'uname -r'",
    )

    result, data = collector.collect_data()

    assert data == KernelDataModel(kernel_version="5.4.0-88-generic")
    assert result.status == ExecutionStatus.OK


def test_run_error(collector, conn_mock):
    collector.system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=1,
        stdout="",
        stderr="Error occurred",
        command="sh -c 'uname -r'",
    )

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.ERROR
    assert data is None
    assert len(collector.result.events) == 1
