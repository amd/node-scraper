import pytest

from errorscraper.connection.inband.inband import CommandArtifact
from errorscraper.enums.executionstatus import ExecutionStatus
from errorscraper.enums.systeminteraction import SystemInteractionLevel
from errorscraper.models.systeminfo import OSFamily
from errorscraper.plugins.inband.authlog.authlog_collector import AuthLogCollector
from errorscraper.plugins.inband.authlog.authlogdata import AuthLogDataModel


@pytest.fixture
def collector(system_info, conn_mock):
    return AuthLogCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


def test_read_auth_log(collector, conn_mock):
    # /var/log/auth.log exists and read successful

    example_auth_log = """Mar 12 01:54:57 example-001 sshd[12345]: example(sshd:account): example.cc: Resolved hostname: hostname
    Mar 12 01:54:57 example-001 sshd[12345]: Accepted publickey for user from 000.000.0.0 port 12345 ssh2: RSA SHA256:example
    Mar 12 01:54:57 example-001 sshd[12345]: example(sshd:session): session opened for user user(uid=0000) by (uid=0)"""

    collector.system_info.os_family = OSFamily.LINUX

    conn_mock.run_command.side_effect = [
        CommandArtifact(
            exit_code=0, stdout="", stderr="", command=f"test -f {collector.AUTH_LOG_PATH}"
        ),
        CommandArtifact(
            exit_code=0,
            stdout=example_auth_log,
            stderr="",
            command=f"cat {collector.AUTH_LOG_PATH}",
        ),
    ]

    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.OK
    assert data == AuthLogDataModel(log_content=example_auth_log)


def test_read_secure_log(collector, conn_mock):
    # /var/log/secure exists and read successful

    example_secure_log = """Mar 12 01:54:57 example-001 sshd[12345]: example(sshd:account): example.cc: Resolved hostname: hostname
    Mar 12 01:54:57 example-001 sshd[12345]: Accepted publickey for user from 000.000.0.0 port 12345 ssh2: RSA SHA256:example
    Mar 12 01:54:57 example-001 sshd[12345]: example(sshd:session): session opened for user user(uid=0000) by (uid=0)"""

    collector.system_info.os_family = OSFamily.LINUX

    conn_mock.run_command.side_effect = [
        CommandArtifact(
            exit_code=1, stdout="", stderr="", command=f"test -f {collector.AUTH_LOG_PATH}"
        ),
        CommandArtifact(
            exit_code=0,
            stdout="",
            stderr="",
            command=f"test -f {collector.SECURE_LOG_PATH}",
        ),
        CommandArtifact(
            exit_code=0,
            stdout=example_secure_log,
            stderr="",
            command=f"cat {collector.SECURE_LOG_PATH}",
        ),
    ]

    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.OK
    assert data == AuthLogDataModel(log_content=example_secure_log)


def test_no_log_files(collector, conn_mock):
    # Neither /var/log/auth.log nor /var/log/secure files exist. Return ExecutionStatus.NOT_RAN

    collector.system_info.os_family = OSFamily.LINUX

    conn_mock.run_command.side_effect = [
        CommandArtifact(
            exit_code=1, stdout="", stderr="", command=f"test -f {collector.AUTH_LOG_PATH}"
        ),
        CommandArtifact(
            exit_code=1,
            stdout="",
            stderr="",
            command=f"test -f {collector.SECURE_LOG_PATH}",
        ),
    ]

    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.NOT_RAN
    assert data is None
