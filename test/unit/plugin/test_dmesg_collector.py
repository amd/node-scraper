import time
from time import sleep as originalsleep

import pytest

from errorscraper.connection.inband.inband import CommandArtifact
from errorscraper.enums.executionstatus import ExecutionStatus
from errorscraper.enums.systeminteraction import SystemInteractionLevel
from errorscraper.interfaces.task import SystemCompatibilityError
from errorscraper.models.systeminfo import OSFamily
from errorscraper.plugins.inband.dmesg.dmesg_collector import DmesgCollector
from errorscraper.plugins.inband.dmesg.dmesgdata import DmesgData


def newsleep(seconds):
    sleep_speed_factor = 10.0
    originalsleep(seconds / sleep_speed_factor)


@pytest.fixture
def setup_dmesg_collector():
    old_sleep = time.sleep
    time.sleep = newsleep
    yield
    time.sleep = old_sleep


def test_get_new_lines():
    """Test the new lines method"""

    initial_dmesg = (
        "2023-06-01T01:00:00,685236-05:00 test message1\n"
        "2023-06-01T02:30:00,685106-05:00 test message2\n"
        "2023-06-01T03:00:00,983214-05:00 test message3\n"
        "2023-06-01T03:20:00,635178-05:00 test message4\n"
        "2023-06-01T03:25:00,635178-05:00 test message5"
    )

    new_dmesg = (
        "2023-06-01T01:00:00,685236-05:00 test message1\n"
        "2023-06-01T02:30:00,685106-05:00 test message2\n"
        "2023-06-01T03:00:00,983214-05:00 test message3\n"
        "2023-06-01T03:20:00,635178-05:00 test message4\n"
        "2023-06-01T03:25:00,635178-05:00 test message5\n"
        "2023-06-01T03:30:00,635178-05:00 test message7\n"
        "2023-06-01T03:35:00,635178-05:00 test message8\n"
        "2023-06-01T03:36:00,635178-05:00 test message9"
    )

    exp_new_lines = (
        "2023-06-01T03:30:00,635178-05:00 test message7\n"
        "2023-06-01T03:35:00,635178-05:00 test message8\n"
        "2023-06-01T03:36:00,635178-05:00 test message9"
    )

    new_lines = DmesgData.get_new_dmesg_lines(initial_dmesg, new_dmesg)

    assert new_lines == exp_new_lines


def test_run_surface(setup_dmesg_collector, system_info, conn_mock):
    """Test the run method."""
    system_info.os_family = OSFamily.LINUX
    collector = DmesgCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.SURFACE,
        connection=conn_mock,
    )

    dmesg = (
        "2023-06-01T01:00:00,685236-05:00 test message1\n"
        "2023-06-01T02:30:00,685106-05:00 test message2\n"
        "2023-06-01T03:00:00,983214-05:00 test message3\n"
        "      kernel:[Hardware Error]: IPID: 0x0001400136430400, Syndrome: 0x0000000000001005\n"
        "      Message from syslogd@pp-128-b6-2 at Feb  8 08:25:18 ...\n"
        "   \n"
        "2023-06-01T03:20:00,635178-05:00 test message4\n"
        "2023-06-01T03:25:00,635178-05:00 test message5\n"
    )
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=0,
        stdout=dmesg,
        stderr="",
        command="dmesg --time-format iso",
    )

    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.OK
    assert data.dmesg_content == dmesg


def test_run_standard_mi300x(setup_dmesg_collector, conn_mock, system_info):
    """Test the run method."""

    dmesg = (
        "2023-06-01T01:00:00,685236-05:00 test message1\n"
        "2023-06-01T02:30:00,685106-05:00 test message2\n"
        "2023-06-01T03:00:00,983214-05:00 test message3\n"
        "      kernel:[Hardware Error]: IPID: 0x0001400136430400, Syndrome: 0x0000000000001005\n"
        "      Message from syslogd@pp-128-b6-2 at Feb  8 08:25:18 ...\n"
        "   \n"
        "2023-06-01T03:20:00,635178-05:00 test message4\n"
        "2023-06-01T03:25:00,635178-05:00 test message5"
    )
    collector = DmesgCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.STANDARD,
        connection=conn_mock,
    )

    outstanding_ras_errors = "de: 0\nue: 0\nce: 0"

    conn_mock.run_command.side_effect = [
        CommandArtifact(
            exit_code=0,
            stdout=dmesg,
            stderr="",
            command="dmesg --time-format iso +x",
        ),
        CommandArtifact(
            exit_code=0,
            stdout="",
            stderr="",
            command="cat /sys/class/drm/*/device/ras/*_err_count",
        ),
        CommandArtifact(
            exit_code=0,
            stdout=outstanding_ras_errors,
            stderr="",
            command="dmesg --time-format iso +x",
        ),
    ]
    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.OK
    # assert data.dmesg_content == dmesg + "\n" + outstanding_ras_errors
    assert data.dmesg_content == dmesg


def test_run_standard_mi300a(setup_dmesg_collector, conn_mock, system_info):
    """Test the run method."""

    dmesg = (
        "2023-06-01T01:00:00,685236-05:00 test message1\n"
        "2023-06-01T02:30:00,685106-05:00 test message2\n"
        "2023-06-01T03:00:00,983214-05:00 test message3\n"
        "      kernel:[Hardware Error]: IPID: 0x0001400136430400, Syndrome: 0x0000000000001005\n"
        "      Message from syslogd@pp-128-b6-2 at Feb  8 08:25:18 ...\n"
        "   \n"
        "2023-06-01T03:20:00,635178-05:00 test message4\n"
        "2023-06-01T03:25:00,635178-05:00 test message5"
    )
    collector = DmesgCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.STANDARD,
        connection=conn_mock,
    )

    # conn_mock.read_file.return_value = FileArtifact(
    #    filename=collector.MACHINE_CHECK_PATH, contents="300"
    # )

    hw_err_1 = "Hardware Error1"
    hw_err_2 = "Hardware Error2"

    conn_mock.run_command.side_effect = [
        CommandArtifact(
            exit_code=0,
            stdout=dmesg,
            stderr="",
            command="dmesg --time-format iso +x",
        ),
        # CommandArtifact(
        #    exit_code=0,
        #    stdout=dmesg,
        #    stderr="",
        #    command=f"test -f {collector.MACHINE_CHECK_PATH}",
        # ),
        # CommandArtifact(
        #    exit_code=0,
        #    stdout="",
        #    stderr="",
        #    command=f"sudo bash -c 'echo 1 > {collector.MACHINE_CHECK_PATH}'",
        # ),
        CommandArtifact(
            exit_code=0,
            stdout=hw_err_1,
            stderr="",
            command="dmesg --time-format iso +x",
        ),
        CommandArtifact(
            exit_code=0,
            stdout=hw_err_2,
            stderr="",
            command="dmesg --time-format iso +x",
        ),
        CommandArtifact(
            exit_code=0,
            stdout="no hw errors",
            stderr="",
            command="dmesg --time-format iso +x",
        ),
        # CommandArtifact(
        #    exit_code=0,
        #    stdout="",
        #    stderr="",
        #    command=f"sudo bash -c 'echo 300 > {collector.MACHINE_CHECK_PATH}'",
        # ),
    ]
    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.OK
    # assert data.dmesg_content == f"{dmesg}\n{hw_err_1}\n{hw_err_2}\nno hw errors"
    assert data.dmesg_content == f"{dmesg}"


def test_bad_exit_code(setup_dmesg_collector, conn_mock, system_info):
    """Test the run method."""

    dmesg = (
        "2023-06-01T01:00:00,685236-05:00 test message1\n"
        "2023-06-01T02:30:00,685106-05:00 test message2\n"
        "2023-06-01T03:00:00,983214-05:00 test message3\n"
        "      kernel:[Hardware Error]: IPID: 0x0001400136430400, Syndrome: 0x0000000000001005\n"
        "      Message from syslogd@pp-128-b6-2 at Feb  8 08:25:18 ...\n"
        "   \n"
        "2023-06-01T03:20:00,635178-05:00 test message4\n"
        "2023-06-01T03:25:00,635178-05:00 test message5\n"
    )
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=1,
        stdout=dmesg,
        stderr="",
        command="dmesg --time-format iso",
    )

    collector = DmesgCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.STANDARD,
        connection=conn_mock,
    )

    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.ERROR


def test_run_dmesg_windows(setup_dmesg_collector, conn_mock, system_info):
    system_info.os_family = OSFamily.WINDOWS
    with pytest.raises(SystemCompatibilityError, match="WINDOWS OS family is not supported"):
        DmesgCollector(
            system_info=system_info,
            system_interaction_level=SystemInteractionLevel.STANDARD,
            connection=conn_mock,
        )


def test_data_model():
    dmesg_data1 = DmesgData.import_model(
        {"dmesg_content": "2023-06-01T01:00:00,685236-05:00 test message1\n"}
    )
    dmesg_data2 = DmesgData.import_model(
        {"dmesg_content": "2023-06-01T02:30:00,685106-05:00 test message2\n"}
    )

    dmesg_data2.merge_data(dmesg_data1)
    assert dmesg_data2.dmesg_content == (
        "2023-06-01T01:00:00,685236-05:00 test message1\n2023-06-01T02:30:00,685106-05:00 test message2"
    )
