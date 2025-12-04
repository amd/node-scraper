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


def test_rocm_package_filtering_default_regex(collector, conn_mock, command_results):
    """Test ROCm package filtering with default regex pattern."""
    # Mock Ubuntu system with ROCm packages
    ubuntu_packages = """rocm-core 5.7.0
                    hip-runtime-amd 5.7.0
                    hsa-rocr 1.9.0
                    amdgpu-dkms 6.3.6
                    gcc 11.4.0
                    python3 3.10.12"""

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
            stdout=ubuntu_packages,
            stderr="",
        ),
    ]

    res, data = collector.collect_data()
    assert res.status == ExecutionStatus.OK
    # Check that ROCm packages are found
    assert "rocm" in res.message.lower()
    assert data is not None
    # Verify all packages are collected
    assert len(data.version_info) == 6


def test_rocm_package_filtering_custom_regex(collector, conn_mock, command_results):
    """Test ROCm package filtering with custom regex pattern."""
    from nodescraper.plugins.inband.package.analyzer_args import PackageAnalyzerArgs

    # Mock Ubuntu system with ROCm packages
    ubuntu_packages = """rocm-core 5.7.0
                    hip-runtime-amd 5.7.0
                    hsa-rocr 1.9.0
                    amdgpu-dkms 6.3.6
                    gcc 11.4.0
                    python3 3.10.12"""

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
            stdout=ubuntu_packages,
            stderr="",
        ),
    ]

    # Use custom regex that only matches 'rocm' and 'hip'
    args = PackageAnalyzerArgs(rocm_regex="rocm|hip")
    res, data = collector.collect_data(args)
    assert res.status == ExecutionStatus.OK
    # Check that ROCm packages are found
    assert "found 2 rocm-related packages" in res.message.lower()
    assert data is not None


def test_rocm_package_filtering_no_matches(collector, conn_mock, command_results):
    """Test ROCm package filtering when no ROCm packages are installed."""
    from nodescraper.plugins.inband.package.analyzer_args import PackageAnalyzerArgs

    # Mock Ubuntu system without ROCm packages
    ubuntu_packages = """gcc 11.4.0
                    python3 3.10.12
                    vim 8.2.3995"""

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
            stdout=ubuntu_packages,
            stderr="",
        ),
    ]

    args = PackageAnalyzerArgs(rocm_regex="rocm|hip|hsa")
    res, data = collector.collect_data(args)
    assert res.status == ExecutionStatus.OK
    # No ROCm packages found, so message should not mention them
    assert "rocm" not in res.message.lower() or res.message == ""
    assert data is not None
    assert len(data.version_info) == 3


def test_filter_rocm_packages_method(collector):
    """Test _filter_rocm_packages method directly."""
    packages = {
        "rocm-core": "5.7.0",
        "hip-runtime-amd": "5.7.0",
        "hsa-rocr": "1.9.0",
        "amdgpu-dkms": "6.3.6",
        "gcc": "11.4.0",
        "python3": "3.10.12",
    }

    # Test with default-like pattern
    rocm_pattern = "rocm|hip|hsa|amdgpu"
    filtered = collector._filter_rocm_packages(packages, rocm_pattern)

    assert len(filtered) == 4
    assert "rocm-core" in filtered
    assert "hip-runtime-amd" in filtered
    assert "hsa-rocr" in filtered
    assert "amdgpu-dkms" in filtered
    assert "gcc" not in filtered
    assert "python3" not in filtered


def test_filter_rocm_packages_case_insensitive(collector):
    """Test that ROCm package filtering is case-insensitive."""
    packages = {
        "ROCM-Core": "5.7.0",
        "HIP-Runtime-AMD": "5.7.0",
        "gcc": "11.4.0",
    }

    rocm_pattern = "rocm|hip"
    filtered = collector._filter_rocm_packages(packages, rocm_pattern)

    assert len(filtered) == 2
    assert "ROCM-Core" in filtered
    assert "HIP-Runtime-AMD" in filtered
