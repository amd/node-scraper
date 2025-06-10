###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
###############################################################################
import json

import pytest

from nodescraper.connection.inband.inband import CommandArtifact
from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.models.systeminfo import OSFamily
from nodescraper.plugins.inband.package.package_collector import PackageCollector


@pytest.fixture
def command_results(plugin_fixtures_path):
    with (plugin_fixtures_path / "package_commands.json").open() as fid:
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
        CommandArtifact(command="", exit_code=0, stdout=command_results["arch_rel"], stderr=""),
        CommandArtifact(
            command="",
            exit_code=0,
            stdout=command_results["arch_package"],
            stderr="",
        ),
    ]
    res, data = collector.collect_data()
    run_assertions(res, data, "test-arch-package-a", "1.11-1")


def test_collector_debian(collector, conn_mock, command_results):
    conn_mock.run_command.side_effect = [
        CommandArtifact(command="", exit_code=0, stdout=command_results["deb_rel"], stderr=""),
        CommandArtifact(
            command="", exit_code=0, stdout=command_results["debian_package"], stderr=""
        ),
    ]
    res, data = collector.collect_data()
    run_assertions(res, data, "test-deb-package-a.x86_64", "3.11-1")


def test_collector_ubuntu(collector, conn_mock, command_results):
    conn_mock.run_command.side_effect = [
        CommandArtifact(
            command="",
            exit_code=0,
            stdout=command_results["ubuntu_rel"],
            stderr="",
        ),
        CommandArtifact(
            command="",
            exit_code=0,
            stdout=command_results["ubuntu_package"],
            stderr="",
        ),
    ]
    res, data = collector.collect_data()
    run_assertions(res, data, "test-ubuntu-package-a.x86_64", "5.11-1")


def test_collector_centos(collector, conn_mock, command_results):
    conn_mock.run_command.side_effect = [
        CommandArtifact(
            command="",
            exit_code=0,
            stdout=command_results["centos_rel"],
            stderr="",
        ),
        CommandArtifact(
            command="",
            exit_code=0,
            stdout=command_results["centos_package"],
            stderr="",
        ),
    ]
    res, data = collector.collect_data()
    run_assertions(res, data, "test-centos-package-a.x86_64", "7.11-1")


def test_collector_fedora(collector, conn_mock, command_results):
    conn_mock.run_command.side_effect = [
        CommandArtifact(
            command="",
            exit_code=0,
            stdout=command_results["fedora_rel"],
            stderr="",
        ),
        CommandArtifact(
            command="",
            exit_code=0,
            stdout=command_results["fedora_package"],
            stderr="",
        ),
    ]
    res, data = collector.collect_data()
    run_assertions(res, data, "test-fed-package-a.x86_64", "9.11-1")


def test_collector_ol8(collector, conn_mock, command_results):
    conn_mock.run_command.side_effect = [
        CommandArtifact(command="", exit_code=0, stdout=command_results["ol8_rel"], stderr=""),
        CommandArtifact(
            command="",
            exit_code=0,
            stdout=command_results["ol8_package"],
            stderr="",
        ),
    ]
    res, data = collector.collect_data()
    run_assertions(res, data, "test-ocl-package-a.x86_64", "11.11-1")


def test_windows(collector, conn_mock, command_results):
    collector.system_info.os_family = OSFamily.WINDOWS
    conn_mock.run_command.side_effect = [
        CommandArtifact(
            command="",
            exit_code=0,
            stdout=command_results["windows_package"],
            stderr="",
        )
    ]
    res, data = collector.collect_data()
    run_assertions(res, data, "Test Windows Package", "11.1.11.1111")


def test_unknown_os(collector):
    collector.system_info.os_family = OSFamily.UNKNOWN
    res, _ = collector.collect_data()
    assert res.status == ExecutionStatus.NOT_RAN
    assert res.message == "Unsupported OS"


def test_unknown_distro(collector, conn_mock, command_results):
    conn_mock.run_command.side_effect = [
        CommandArtifact(command="", exit_code=0, stdout="help", stderr=""),
        CommandArtifact(
            command="",
            exit_code=0,
            stdout=command_results["ol8_package"],
            stderr="",
        ),
    ]
    res, _ = collector.collect_data()
    assert res.status == ExecutionStatus.NOT_RAN


def test_bad_exit_code(collector, conn_mock, command_results):
    conn_mock.run_command.side_effect = [
        CommandArtifact(command="", exit_code=1, stdout=command_results["ol8_rel"], stderr=""),
        CommandArtifact(
            command="",
            exit_code=1,
            stdout=command_results["ol8_package"],
            stderr="",
        ),
    ]
    res, _ = collector.collect_data()
    assert res.status == ExecutionStatus.EXECUTION_FAILURE


def test_bad_splits_ubuntu(collector, conn_mock, command_results):
    conn_mock.run_command.side_effect = [
        CommandArtifact(
            command="",
            exit_code=0,
            stdout=command_results["ubuntu_rel"],
            stderr="",
        ),
        CommandArtifact(
            command="",
            exit_code=0,
            stdout="something: 1.0.0 something something\n",
            stderr="",
        ),
    ]
    res, _ = collector.collect_data()
    assert res.status == ExecutionStatus.OK
