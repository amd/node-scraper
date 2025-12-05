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
"""
Test suite for all analyzer_args build_from_model methods.
Ensures that build_from_model includes all required fields.
"""

from nodescraper.plugins.inband.bios.analyzer_args import BiosAnalyzerArgs
from nodescraper.plugins.inband.bios.biosdata import BiosDataModel
from nodescraper.plugins.inband.cmdline.analyzer_args import CmdlineAnalyzerArgs
from nodescraper.plugins.inband.cmdline.cmdlinedata import CmdlineDataModel
from nodescraper.plugins.inband.device_enumeration.analyzer_args import (
    DeviceEnumerationAnalyzerArgs,
)
from nodescraper.plugins.inband.device_enumeration.deviceenumdata import (
    DeviceEnumerationDataModel,
)
from nodescraper.plugins.inband.dkms.analyzer_args import DkmsAnalyzerArgs
from nodescraper.plugins.inband.dkms.dkmsdata import DkmsDataModel
from nodescraper.plugins.inband.kernel.analyzer_args import KernelAnalyzerArgs
from nodescraper.plugins.inband.kernel.kerneldata import KernelDataModel
from nodescraper.plugins.inband.kernel_module.analyzer_args import (
    KernelModuleAnalyzerArgs,
)
from nodescraper.plugins.inband.kernel_module.kernel_module_data import (
    KernelModuleDataModel,
)
from nodescraper.plugins.inband.os.analyzer_args import OsAnalyzerArgs
from nodescraper.plugins.inband.os.osdata import OsDataModel
from nodescraper.plugins.inband.package.analyzer_args import PackageAnalyzerArgs
from nodescraper.plugins.inband.package.packagedata import PackageDataModel
from nodescraper.plugins.inband.process.analyzer_args import ProcessAnalyzerArgs
from nodescraper.plugins.inband.process.processdata import ProcessDataModel
from nodescraper.plugins.inband.rocm.analyzer_args import RocmAnalyzerArgs
from nodescraper.plugins.inband.rocm.rocmdata import RocmDataModel
from nodescraper.plugins.inband.sysctl.analyzer_args import SysctlAnalyzerArgs
from nodescraper.plugins.inband.sysctl.sysctldata import SysctlDataModel


def test_package_analyzer_args_build_from_model():
    """Test PackageAnalyzerArgs.build_from_model includes all fields"""
    datamodel = PackageDataModel(version_info={"package1": "1.0.0", "package2": "2.0.0"})
    args = PackageAnalyzerArgs.build_from_model(datamodel)

    assert isinstance(args, PackageAnalyzerArgs)
    assert args.exp_package_ver == {"package1": "1.0.0", "package2": "2.0.0"}


def test_device_enumeration_analyzer_args_build_from_model():
    """Test DeviceEnumerationAnalyzerArgs.build_from_model includes all fields"""
    datamodel = DeviceEnumerationDataModel(cpu_count=2, gpu_count=8, vf_count=0)
    args = DeviceEnumerationAnalyzerArgs.build_from_model(datamodel)

    assert isinstance(args, DeviceEnumerationAnalyzerArgs)
    assert args.cpu_count == [2]
    assert args.gpu_count == [8]
    assert args.vf_count == [0]


def test_device_enumeration_analyzer_args_build_from_model_with_none():
    """Test DeviceEnumerationAnalyzerArgs.build_from_model with None values"""
    datamodel = DeviceEnumerationDataModel(cpu_count=None, gpu_count=4, vf_count=None)
    args = DeviceEnumerationAnalyzerArgs.build_from_model(datamodel)

    assert isinstance(args, DeviceEnumerationAnalyzerArgs)
    assert args.cpu_count is None
    assert args.gpu_count == [4]
    assert args.vf_count is None


def test_kernel_analyzer_args_build_from_model():
    """Test KernelAnalyzerArgs.build_from_model includes all fields"""
    datamodel = KernelDataModel(
        kernel_info="Linux hostname 5.15.0-56-generic #62-Ubuntu SMP x86_64 GNU/Linux",
        kernel_version="5.15.0-56-generic",
    )
    args = KernelAnalyzerArgs.build_from_model(datamodel)

    assert isinstance(args, KernelAnalyzerArgs)
    assert args.exp_kernel == ["5.15.0-56-generic"]


def test_rocm_analyzer_args_build_from_model():
    """Test RocmAnalyzerArgs.build_from_model includes all fields"""
    datamodel = RocmDataModel(rocm_version="5.4.0", rocm_latest_versioned_path="/opt/rocm-5.4.0")
    args = RocmAnalyzerArgs.build_from_model(datamodel)

    assert isinstance(args, RocmAnalyzerArgs)
    assert args.exp_rocm == ["5.4.0"]
    assert args.exp_rocm_latest == "/opt/rocm-5.4.0"


def test_os_analyzer_args_build_from_model():
    """Test OsAnalyzerArgs.build_from_model includes all fields"""
    datamodel = OsDataModel(os_name="Ubuntu 22.04", os_version="22.04")
    args = OsAnalyzerArgs.build_from_model(datamodel)

    assert isinstance(args, OsAnalyzerArgs)
    assert args.exp_os == ["Ubuntu 22.04"]


def test_bios_analyzer_args_build_from_model():
    """Test BiosAnalyzerArgs.build_from_model includes all fields"""
    datamodel = BiosDataModel(bios_version="1.2.3")
    args = BiosAnalyzerArgs.build_from_model(datamodel)

    assert isinstance(args, BiosAnalyzerArgs)
    assert args.exp_bios_version == ["1.2.3"]


def test_cmdline_analyzer_args_build_from_model():
    """Test CmdlineAnalyzerArgs.build_from_model includes all fields"""
    datamodel = CmdlineDataModel(cmdline="iommu=pt intel_iommu=on")
    args = CmdlineAnalyzerArgs.build_from_model(datamodel)

    assert isinstance(args, CmdlineAnalyzerArgs)
    assert args.required_cmdline == ["iommu=pt intel_iommu=on"]


def test_dkms_analyzer_args_build_from_model():
    """Test DkmsAnalyzerArgs.build_from_model includes all fields"""
    datamodel = DkmsDataModel(status="installed", version="6.8.5-6.8.5")
    args = DkmsAnalyzerArgs.build_from_model(datamodel)

    assert isinstance(args, DkmsAnalyzerArgs)
    assert args.dkms_status == ["installed"]
    assert args.dkms_version == ["6.8.5-6.8.5"]


def test_sysctl_analyzer_args_build_from_model():
    """Test SysctlAnalyzerArgs.build_from_model includes all fields"""
    datamodel = SysctlDataModel(
        vm_swappiness=60,
        vm_numa_balancing=1,
        vm_oom_kill_allocating_task=0,
        vm_compaction_proactiveness=20,
        vm_compact_unevictable_allowed=1,
        vm_extfrag_threshold=500,
        vm_zone_reclaim_mode=0,
        vm_dirty_background_ratio=10,
        vm_dirty_ratio=20,
        vm_dirty_writeback_centisecs=500,
        kernel_numa_balancing=1,
    )
    args = SysctlAnalyzerArgs.build_from_model(datamodel)

    assert isinstance(args, SysctlAnalyzerArgs)
    assert args.exp_vm_swappiness == 60
    assert args.exp_vm_numa_balancing == 1
    assert args.exp_vm_oom_kill_allocating_task == 0
    assert args.exp_vm_compaction_proactiveness == 20
    assert args.exp_vm_compact_unevictable_allowed == 1
    assert args.exp_vm_extfrag_threshold == 500
    assert args.exp_vm_zone_reclaim_mode == 0
    assert args.exp_vm_dirty_background_ratio == 10
    assert args.exp_vm_dirty_ratio == 20
    assert args.exp_vm_dirty_writeback_centisecs == 500
    assert args.exp_kernel_numa_balancing == 1


def test_process_analyzer_args_build_from_model():
    """Test ProcessAnalyzerArgs.build_from_model includes all fields"""
    datamodel = ProcessDataModel(kfd_process=5, cpu_usage=15.5)
    args = ProcessAnalyzerArgs.build_from_model(datamodel)

    assert isinstance(args, ProcessAnalyzerArgs)
    assert args.max_kfd_processes == 5
    assert args.max_cpu_usage == 15.5


def test_kernel_module_analyzer_args_build_from_model():
    """Test KernelModuleAnalyzerArgs.build_from_model includes all fields"""
    datamodel = KernelModuleDataModel(
        kernel_modules={
            "amdgpu": {"size": 1024, "used": 0},
            "amd_iommu": {"size": 512, "used": 1},
            "other_module": {"size": 256, "used": 0},
        }
    )
    args = KernelModuleAnalyzerArgs.build_from_model(datamodel)

    assert isinstance(args, KernelModuleAnalyzerArgs)
    assert "amdgpu" in args.kernel_modules
    assert "amd_iommu" in args.kernel_modules
    assert "other_module" not in args.kernel_modules
    assert args.regex_filter == []
