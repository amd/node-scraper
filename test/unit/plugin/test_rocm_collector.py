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
from unittest.mock import MagicMock

import pytest

from nodescraper.enums.eventcategory import EventCategory
from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.plugins.inband.rocm.rocm_collector import RocmCollector


@pytest.fixture
def collector(system_info, conn_mock):
    return RocmCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


def test_collect_rocm_version_success(collector):
    """Test successful collection of ROCm version from version-rocm file"""
    collector._run_sut_cmd = MagicMock(
        return_value=MagicMock(
            exit_code=0,
            stdout="6.2.0-66",
            command="grep . /opt/rocm/.info/version-rocm",
        )
    )

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert data.rocm_version == "6.2.0-66"
    assert "ROCm version: 6.2.0-66" in result.message


def test_collect_rocm_version_fallback(collector):
    """Test fallback to version file when version-rocm fails"""
    collector._run_sut_cmd = MagicMock(
        side_effect=[
            # Sub-versions (grep . -r /opt/rocm/.info/*)
            MagicMock(exit_code=0, stdout=""),
            # First path: version-rocm (fails)
            MagicMock(exit_code=1, stdout="", command="grep . /opt/rocm/.info/version-rocm"),
            # Second path: version (succeeds)
            MagicMock(exit_code=0, stdout="6.2.0-66", command="grep . /opt/rocm/.info/version"),
            # Additional commands after finding version
            MagicMock(exit_code=1, stdout=""),  # latest path
            MagicMock(exit_code=1, stdout=""),  # all paths
            MagicMock(exit_code=1, stdout=""),  # rocminfo
            MagicMock(exit_code=1, stdout=""),  # ld.so.conf
            MagicMock(exit_code=1, stdout=""),  # rocm_libs
            MagicMock(exit_code=1, stdout=""),  # env_vars
            MagicMock(exit_code=1, stdout=""),  # clinfo
            MagicMock(exit_code=1, stdout=""),  # kfd_proc
        ]
    )

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert data.rocm_version == "6.2.0-66"


def test_collect_rocm_version_not_found(collector):
    """Test when ROCm version cannot be found"""
    collector._run_sut_cmd = MagicMock(
        return_value=MagicMock(
            exit_code=1,
            stdout="",
            stderr="No such file or directory",
            command="grep . /opt/rocm/.info/version-rocm",
        )
    )

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.ERROR
    assert data is None
    assert "ROCm version not found" in result.message
    assert any(event.category == EventCategory.OS.value for event in result.events)


def test_collect_all_rocm_data(collector):
    """Test collection of all ROCm data including tech support commands"""
    # Mock all command outputs in sequence (order must match collector's call order)
    collector._run_sut_cmd = MagicMock(
        side_effect=[
            # Sub-versions (grep . -r /opt/rocm/.info/*)
            MagicMock(exit_code=0, stdout="/opt/rocm/.info/version-rocm:6.2.0-66"),
            # ROCm version (grep . /opt/rocm/.info/version-rocm)
            MagicMock(exit_code=0, stdout="6.2.0-66"),
            # Latest versioned path
            MagicMock(exit_code=0, stdout="/opt/rocm-1.1.0"),
            # All ROCm paths
            MagicMock(exit_code=0, stdout="/opt/rocm\n/opt/rocm-1.2.3\n/opt/rocm-5.6.0"),
            # rocminfo output
            MagicMock(
                exit_code=0,
                stdout="ROCk module is loaded\nAgent 1\n  Name: AMD Instinct MI1234XYZ\n  Marketing Name: MI1234XYZ",
            ),
            # ld.so.conf entries
            MagicMock(
                exit_code=0,
                stdout="/etc/ld.so.conf.d/10-rocm-opencl.conf:/opt/rocm-7.0.0/lib\n/etc/ld.so.conf.d/10-rocm-opencl.conf:/opt/rocm-7.0.0/lib64",
            ),
            # ROCm libraries from ldconfig
            MagicMock(
                exit_code=0,
                stdout="librocm_smi64.so.7 (libc6,x86-64) => /opt/rocm/lib/librocm_smi64.so.7\nlibhsa-runtime64.so.1 (libc6,x86-64) => /opt/rocm/lib/libhsa-runtime64.so.1",
            ),
            # Environment variables
            MagicMock(
                exit_code=0,
                stdout="ROCM_PATH=/opt/rocm\nSLURM_MPI_TYPE=pmi2\n__LMOD_REF_COUNT_MODULEPATH=/share/contrib-modules/.mfiles/Core:1\nMODULEPATH=/share/contrib-modules/",
            ),
            # clinfo output
            MagicMock(
                exit_code=0,
                stdout="Number of platforms: 1\nPlatform Name: AMD Accelerated Parallel Processing\nPlatform Vendor: Advanced Micro Devices, Inc.\nPlatform Version: OpenCL 2.0 AMD-APP (XXXX.X)\nPlatform Profile: FULL_PROFILE\nPlatform Extensions: cl_khr_icd cl_khr_il_program",
            ),
            # KFD process list
            MagicMock(exit_code=0, stdout="1234\n5678"),
        ]
    )

    result, data = collector.collect_data()

    # Verify result status
    assert result.status == ExecutionStatus.OK
    assert data is not None

    # Verify ROCm version
    assert data.rocm_version == "6.2.0-66"

    # Verify ROCm latest path
    assert data.rocm_latest_versioned_path == "/opt/rocm-1.1.0"

    # Verify all ROCm paths
    assert data.rocm_all_paths == ["/opt/rocm", "/opt/rocm-1.2.3", "/opt/rocm-5.6.0"]

    # Verify rocminfo output
    assert len(data.rocminfo) == 4
    assert "ROCk module is loaded" in data.rocminfo[0]
    assert "AMD Instinct MI1234XYZ" in data.rocminfo[2]

    # Verify ld.so.conf entries
    assert len(data.ld_conf_rocm) == 2
    assert "/etc/ld.so.conf.d/10-rocm-opencl.conf:/opt/rocm-7.0.0/lib" in data.ld_conf_rocm
    assert "/etc/ld.so.conf.d/10-rocm-opencl.conf:/opt/rocm-7.0.0/lib64" in data.ld_conf_rocm

    # Verify ROCm libraries
    assert len(data.rocm_libs) == 2
    assert any("librocm_smi64" in lib for lib in data.rocm_libs)
    assert any("libhsa-runtime64" in lib for lib in data.rocm_libs)

    # Verify environment variables
    assert len(data.env_vars) == 4
    assert "ROCM_PATH=/opt/rocm" in data.env_vars
    assert "MODULEPATH=/share/contrib-modules/" in data.env_vars

    # Verify clinfo output
    assert len(data.clinfo) == 6
    assert "AMD Accelerated Parallel Processing" in data.clinfo[1]

    # Verify KFD process list
    assert len(data.kfd_proc) == 2
    assert "1234" in data.kfd_proc
    assert "5678" in data.kfd_proc

    # Verify artifact was created
    assert len(result.artifacts) == 1
    assert result.artifacts[0].filename == "rocminfo.log"
    assert "ROCMNFO OUTPUT" in result.artifacts[0].contents
    assert "CLINFO OUTPUT" in result.artifacts[0].contents


def test_collect_with_clinfo_failure(collector):
    """Test that clinfo failure is handled gracefully and captured in artifact"""
    collector._run_sut_cmd = MagicMock(
        side_effect=[
            # Sub-versions (grep . -r /opt/rocm/.info/*)
            MagicMock(exit_code=0, stdout="/opt/rocm/.info/version-rocm:6.2.0-66"),
            # ROCm version (grep . /opt/rocm/.info/version-rocm)
            MagicMock(exit_code=0, stdout="6.2.0-66"),
            # Latest versioned path
            MagicMock(exit_code=0, stdout="/opt/rocm-7.1.0"),
            # All ROCm paths
            MagicMock(exit_code=0, stdout="/opt/rocm"),
            # rocminfo success
            MagicMock(exit_code=0, stdout="ROCk module loaded"),
            # Other commands
            MagicMock(exit_code=1, stdout=""),
            MagicMock(exit_code=1, stdout=""),
            MagicMock(exit_code=1, stdout=""),
            # clinfo failure
            MagicMock(
                exit_code=127,
                stdout="",
                stderr="No such file or directory",
                command="/opt/rocm-7.1.0/opencl/bin/*/clinfo",
            ),
            # kfd_proc
            MagicMock(exit_code=0, stdout=""),
        ]
    )

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.OK
    assert data.clinfo == []

    # Verify artifact contains error information
    assert len(result.artifacts) == 1
    artifact_content = result.artifacts[0].contents
    assert "CLINFO OUTPUT" in artifact_content
    assert "Exit Code: 127" in artifact_content
    assert "No such file or directory" in artifact_content


def test_collect_minimal_data(collector):
    """Test collection when only version is available"""
    collector._run_sut_cmd = MagicMock(
        side_effect=[
            # Sub-versions (grep . -r /opt/rocm/.info/*)
            MagicMock(exit_code=0, stdout=""),
            # ROCm version (grep . /opt/rocm/.info/version-rocm)
            MagicMock(exit_code=0, stdout="6.2.0-66"),
            # All subsequent commands fail
            MagicMock(exit_code=1, stdout=""),  # latest path
            MagicMock(exit_code=1, stdout=""),  # all paths
            MagicMock(exit_code=1, stdout=""),  # rocminfo
            MagicMock(exit_code=1, stdout=""),  # ld.so.conf
            MagicMock(exit_code=1, stdout=""),  # rocm_libs
            MagicMock(exit_code=1, stdout=""),  # env_vars
            MagicMock(exit_code=1, stdout=""),  # clinfo
            MagicMock(exit_code=1, stdout=""),  # kfd_proc
        ]
    )

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert data.rocm_version == "6.2.0-66"

    # Verify optional fields have default values
    assert data.rocm_latest_versioned_path == ""
    assert data.rocm_all_paths == []
    assert data.rocminfo == []
    assert data.ld_conf_rocm == []
    assert data.rocm_libs == []
    assert data.env_vars == []
    assert data.clinfo == []
    assert data.kfd_proc == []


def test_invalid_rocm_version_format(collector):
    """Test that invalid ROCm version format is handled gracefully"""
    collector._run_sut_cmd = MagicMock(
        return_value=MagicMock(
            exit_code=0,
            stdout="invalid_version_format",
        )
    )

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.ERROR
    assert data is None
    assert len(result.events) >= 1


def test_collect_rocm_sub_versions(collector):
    """Test collection of ROCm version and multiple sub-versions (mirrors error-scraper test_run_new_version)."""
    sub_versions_stdout = (
        "/opt/rocm/.info/version:6.4.0-47\n"
        "/opt/rocm/.info/version-hip-libraries:6.4.0-47\n"
        "/opt/rocm/.info/version-hiprt:6.4.0-47\n"
        "/opt/rocm/.info/version-hiprt-devel:6.4.0-47\n"
        "/opt/rocm/.info/version-hip-sdk:6.4.0-47\n"
        "/opt/rocm/.info/version-lrt:6.4.0-47\n"
        "/opt/rocm/.info/version-ml-libraries:6.4.0-47\n"
        "/opt/rocm/.info/version-ml-sdk:6.4.0-47\n"
        "/opt/rocm/.info/version-oclrt:6.4.0-47\n"
        "/opt/rocm/.info/version-ocl-sdk:6.4.0-47\n"
        "/opt/rocm/.info/version-openmp-sdk:6.4.0-47\n"
        "/opt/rocm/.info/version-rocm:6.4.0-47\n"
        "/opt/rocm/.info/version-rocm-developer-tools:6.4.0-47\n"
        "/opt/rocm/.info/version-utils:6.4.0-47\n"
    )
    expected_sub_versions = {
        "version": "6.4.0-47",
        "version-hip-libraries": "6.4.0-47",
        "version-hiprt": "6.4.0-47",
        "version-hiprt-devel": "6.4.0-47",
        "version-hip-sdk": "6.4.0-47",
        "version-lrt": "6.4.0-47",
        "version-ml-libraries": "6.4.0-47",
        "version-ml-sdk": "6.4.0-47",
        "version-oclrt": "6.4.0-47",
        "version-ocl-sdk": "6.4.0-47",
        "version-openmp-sdk": "6.4.0-47",
        "version-rocm": "6.4.0-47",
        "version-rocm-developer-tools": "6.4.0-47",
        "version-utils": "6.4.0-47",
    }
    collector._run_sut_cmd = MagicMock(
        side_effect=[
            # First: grep . -r /opt/rocm/.info/* (sub-versions)
            MagicMock(exit_code=0, stdout=sub_versions_stdout),
            # Second: grep . /opt/rocm/.info/version-rocm (main version)
            MagicMock(exit_code=0, stdout="6.4.0-47"),
            # Optional data (all fail for minimal test)
            MagicMock(exit_code=1, stdout=""),  # latest path
            MagicMock(exit_code=1, stdout=""),  # all paths
            MagicMock(exit_code=1, stdout=""),  # rocminfo
            MagicMock(exit_code=1, stdout=""),  # ld.so.conf
            MagicMock(exit_code=1, stdout=""),  # rocm_libs
            MagicMock(exit_code=1, stdout=""),  # env_vars
            MagicMock(exit_code=1, stdout=""),  # clinfo
            MagicMock(exit_code=1, stdout=""),  # kfd_proc
        ]
    )

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert data.rocm_version == "6.4.0-47"
    assert data.rocm_sub_versions == expected_sub_versions
    assert any(event.category == "ROCM_VERSION_READ" for event in result.events)
    assert "ROCm version: 6.4.0-47" in result.message
