from unittest.mock import MagicMock

import pytest

from errorscraper.enums.executionstatus import ExecutionStatus
from errorscraper.enums.systeminteraction import SystemInteractionLevel
from errorscraper.interfaces.task import SystemCompatibilityError
from errorscraper.models.systeminfo import OSFamily
from errorscraper.plugins.inband.dkms.dkms_collector import DkmsCollector
from errorscraper.plugins.inband.dkms.dkmsdata import DkmsDataModel


@pytest.fixture
def collector(system_info, conn_mock):
    return DkmsCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.SURFACE,
        connection=conn_mock,
    )


def test_run_linux(collector):
    collector.system_info.os_family = OSFamily.LINUX

    collector._run_sut_cmd = MagicMock()
    collector._run_sut_cmd.side_effect = [
        MagicMock(
            exit_code=0,
            stdout=(
                "amdgpu/6.8.5-2009582.22.04, 5.15.0-117-generic, x86_64: installed\n"
                "amdgpu/6.8.5-2009582.22.04, 5.15.0-91-generic, x86_64: installed"
            ),
        ),
        MagicMock(exit_code=0, stdout="dkms-2.8.7"),
    ]

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.OK
    expected_data = DkmsDataModel(
        status=(
            "amdgpu/6.8.5-2009582.22.04, 5.15.0-117-generic, x86_64: installed\n"
            "amdgpu/6.8.5-2009582.22.04, 5.15.0-91-generic, x86_64: installed"
        ),
        version="dkms-2.8.7",
    )
    assert data == expected_data


def test_run_windows(conn_mock, system_info):
    system_info.os_family = OSFamily.WINDOWS

    with pytest.raises(SystemCompatibilityError):
        DkmsCollector(
            system_info=system_info,
            system_interaction_level=SystemInteractionLevel.SURFACE,
            connection=conn_mock,
        )
