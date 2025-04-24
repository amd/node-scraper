import json

import pytest

from errorscraper.connection.inband.inband import CommandArtifact
from errorscraper.enums.executionstatus import ExecutionStatus
from errorscraper.enums.systeminteraction import SystemInteractionLevel
from errorscraper.models.systeminfo import OSFamily
from errorscraper.plugins.inband.package.package_collector import PackageCollector


@pytest.fixture
def command_results(fixtures_path):
    with (fixtures_path / "package_commands.json").open() as fid:
        return json.load(fid)


@pytest.fixture
def collector(conn_mock, system_info):
    return PackageCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


def run_assertions(res, data, key, expected_version):
    assert res.status == ExecutionStatus.OK
    assert key in data.version_info
    assert data.version_info[key] == expected_version
    for k, v in data.version_info.items():
        assert k is not None
        assert v is not None
        assert "warning" not in k
        assert "warning" not in v


def test_collector_arch(collector, conn_mock, command_results):
    conn_mock.run_command.side_effect = [
        CommandArtifact(
            command="cat /etc/*release", exit_code=0, stdout=command_results["arch_rel"], stderr=""
        ),
        CommandArtifact(
            command="yum list --installed",
            exit_code=0,
            stdout=command_results["arch_package"],
            stderr="",
        ),
    ]
    res, data = collector.collect_data()
    run_assertions(res, data, "argon2", "20190702-6")


def test_collector_debian(collector, conn_mock, command_results):
    conn_mock.run_command.side_effect = [
        CommandArtifact(
            command="cat /etc/*release", exit_code=0, stdout=command_results["deb_rel"], stderr=""
        ),
        CommandArtifact(
            command="dpkg -l", exit_code=0, stdout=command_results["debian_package"], stderr=""
        ),
    ]
    res, data = collector.collect_data()
    run_assertions(res, data, "base-files", "12.4+deb12u8")


def test_collector_ubuntu(collector, conn_mock, command_results):
    conn_mock.run_command.side_effect = [
        CommandArtifact(
            command="cat /etc/*release",
            exit_code=0,
            stdout=command_results["ubuntu_rel"],
            stderr="",
        ),
        CommandArtifact(
            command="yum list --installed",
            exit_code=0,
            stdout=command_results["ubuntu_package"],
            stderr="",
        ),
    ]
    res, data = collector.collect_data()
    run_assertions(res, data, "authselect-libs.x86_64", "1.5.0-8.fc41")


def test_collector_centos(collector, conn_mock, command_results):
    conn_mock.run_command.side_effect = [
        CommandArtifact(
            command="cat /etc/*release",
            exit_code=0,
            stdout=command_results["centos_rel"],
            stderr="",
        ),
        CommandArtifact(
            command="yum list --installed",
            exit_code=0,
            stdout=command_results["centos_package"],
            stderr="",
        ),
    ]
    res, data = collector.collect_data()
    run_assertions(res, data, "bind-export-libs.x86_64", "32:9.11.26-3.el8")


def test_collector_fedora(collector, conn_mock, command_results):
    conn_mock.run_command.side_effect = [
        CommandArtifact(
            command="cat /etc/*release",
            exit_code=0,
            stdout=command_results["fedora_rel"],
            stderr="",
        ),
        CommandArtifact(
            command="yum list --installed",
            exit_code=0,
            stdout=command_results["fedora_package"],
            stderr="",
        ),
    ]
    res, data = collector.collect_data()
    run_assertions(res, data, "bzip2.x86_64", "1.0.8-19.fc41")


def test_collector_ol8(collector, conn_mock, command_results):
    conn_mock.run_command.side_effect = [
        CommandArtifact(
            command="cat /etc/*release", exit_code=0, stdout=command_results["ol8_rel"], stderr=""
        ),
        CommandArtifact(
            command="yum list --installed",
            exit_code=0,
            stdout=command_results["ol8_package"],
            stderr="",
        ),
    ]
    res, data = collector.collect_data()
    run_assertions(res, data, "NetworkManager-tui.x86_64", "1:1.40.16-15.0.1.el8_9")


def test_windows(collector, conn_mock, command_results):
    collector.system_info.os_family = OSFamily.WINDOWS
    conn_mock.run_command.side_effect = [
        CommandArtifact(
            command="wmic product get name, version",
            exit_code=0,
            stdout=command_results["windows_package"],
            stderr="",
        )
    ]
    res, data = collector.collect_data()
    run_assertions(res, data, "Microsoft Policy Platform", "68.1.9086.1017")


def test_unknown_os(collector):
    collector.system_info.os_family = OSFamily.UNKNOWN
    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.NOT_RAN
    assert res.message == "Unsupported OS"


def test_unknown_distro(collector, conn_mock, command_results):
    conn_mock.run_command.side_effect = [
        CommandArtifact(command="cat /etc/*release", exit_code=0, stdout="help", stderr=""),
        CommandArtifact(
            command="yum list --installed",
            exit_code=0,
            stdout=command_results["ol8_package"],
            stderr="",
        ),
    ]
    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.NOT_RAN


def test_bad_exit_code(collector, conn_mock, command_results):
    conn_mock.run_command.side_effect = [
        CommandArtifact(
            command="cat /etc/*release", exit_code=1, stdout=command_results["ol8_rel"], stderr=""
        ),
        CommandArtifact(
            command="yum list --installed",
            exit_code=1,
            stdout=command_results["ol8_package"],
            stderr="",
        ),
    ]
    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.EXECUTION_FAILURE


def test_bad_splits_ubuntu(collector, conn_mock, command_results):
    conn_mock.run_command.side_effect = [
        CommandArtifact(
            command="cat /etc/*release",
            exit_code=0,
            stdout=command_results["ubuntu_rel"],
            stderr="",
        ),
        CommandArtifact(
            command="yum list --installed",
            exit_code=0,
            stdout="something: 1.0.0 something something\n",
            stderr="",
        ),
    ]
    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.OK
