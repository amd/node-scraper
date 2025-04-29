import pytest

from errorscraper.connection.inband.inband import CommandArtifact
from errorscraper.enums.executionstatus import ExecutionStatus
from errorscraper.enums.systeminteraction import SystemInteractionLevel
from errorscraper.models.systeminfo import OSFamily
from errorscraper.plugins.inband.user.user_collector import UserCollector
from errorscraper.plugins.inband.user.userdata import UserDataModel


@pytest.fixture
def collector(system_info, conn_mock):
    return UserCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


def test_who_linux(collector, conn_mock):
    collector.system_info.os_family = OSFamily.LINUX
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=0,
        stdout=(
            "user1      pts/5        2024-09-29 13:36 (11.222.33.444)\n"
            "user1      pts/10       2024-09-18 15:08 (tmux(3048684).%0)\n"
            "root     pts/11       2024-09-27 13:52 (tmux(840941).%0)\n"
        ),
        stderr="",
        command="who",
    )
    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.OK
    assert data == UserDataModel(active_users=["user1", "user1", "root"])


def test_query_users_windows(collector, conn_mock):
    collector.system_info.os_family = OSFamily.WINDOWS
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=0,
        stdout=(
            " USERNAME              SESSIONNAME        ID  STATE   IDLE TIME  LOGON TIME\n"
            ">Administrator              \\console             1  Active      none   4/01/2024 4:20 PM\n"
            "Administrator              console             1  Active      none   4/01/2024 4:20 PM\n"
        ),
        stderr="",
        command="query user",
    )
    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.OK
    assert data == UserDataModel(active_users=["Administrator", "Administrator"])


@pytest.mark.parametrize(
    "os_family, cmd",
    [
        (OSFamily.WINDOWS, "query user"),
        (OSFamily.LINUX, "who"),
    ],
)
def test_command_failure(collector, conn_mock, os_family, cmd):
    collector.system_info.os_family = os_family
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=1,
        stdout="",
        stderr="command failed",
        command=cmd,
    )
    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.EXECUTION_FAILURE
    assert data is None


@pytest.mark.parametrize(
    "os_family, cmd",
    [
        (OSFamily.WINDOWS, "query user"),
        (OSFamily.LINUX, "who"),
    ],
)
def test_no_output(collector, conn_mock, os_family, cmd):
    collector.system_info.os_family = os_family
    conn_mock.run_command.return_value = CommandArtifact(
        exit_code=0,
        stdout="",
        stderr="",
        command=cmd,
    )
    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.OK
    # no active users found
    assert data == UserDataModel(active_users=[])
