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

from types import SimpleNamespace

import pytest

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.plugins.inband.kernel_module.kernel_module_collector import (
    KernelModuleCollector,
)
from nodescraper.plugins.inband.kernel_module.kernel_module_data import (
    KernelModuleDataModel,
    ModuleInfo,
)


@pytest.fixture
def modinfo_amdgpu_full():
    """Fixture providing comprehensive dummy modinfo amdgpu output for testing."""
    return """filename:       /lib/modules/1.2.3-test-kernel/extra/amdgpu_test.ko.xz
version:        99.88.77
license:        GPL and additional rights
description:    AMD GPU Test Module
author:         Test Author One
firmware:       amdgpu/test_gpu_info_v1.bin
firmware:       amdgpu/test_gpu_info_v2.bin
firmware:       amdgpu/dummy_gpu_info_a.bin
firmware:       amdgpu/dummy_gpu_info_b.bin
firmware:       amdgpu/fake_gpu_info_c.bin
firmware:       amdgpu/sample_gpu_info_d.bin
firmware:       amdgpu/example_gpu_info_e.bin
firmware:       amdgpu/mock_gpu_info_f.bin
firmware:       amdgpu/test_gpu_info_g.bin
firmware:       amdgpu/dummy_gpu_info_h.bin
firmware:       amdgpu/fake_gpu_info_i.bin
firmware:       amdgpu/sample_gpu_info_j.bin
srcversion:     ABCD1234567890TESTVER
depends:        dummy_dep1,dummy_dep2,test_dep3,fake_dep4,sample_dep5,example_dep6,mock_dep7
retpoline:      Y
intree:         Y
name:           amdgpu
vermagic:       1.2.3-test-kernel SMP mod_unload modversions
sig_id:         TEST#99
signer:         Test Signing Authority (dummy key 1)
sig_key:        00:11:22:33:44:55:66:77:88:99:AA:BB:CC:DD:EE:FF:00:11:22:33
sig_hashalgo:   test256
parm:           test_param1:Test parameter description one (int)
parm:           test_param2:Test parameter description two (int)
parm:           dummy_param3:Dummy parameter description (uint)
parm:           fake_param4:Fake parameter description (int)
parm:           sample_param5:Sample parameter description (int)
parm:           example_param6:Example parameter (int)
parm:           mock_param7:Mock parameter (int)
parm:           test_audio:Test audio parameter (int)
parm:           dummy_priority:Dummy priority parameter (int)
parm:           fake_i2c:Fake i2c parameter (int)
parm:           sample_gen_cap:Sample gen caps parameter (uint)
parm:           example_msi:Example MSI parameter (int)
parm:           mock_timeout:Mock timeout parameter (string)
parm:           test_dpm:Test DPM parameter (int)
parm:           dummy_fw_load:Dummy firmware load parameter (int)
parm:           fake_aspm:Fake ASPM parameter (int)
parm:           sample_runpm:Sample runtime PM parameter (int)
parm:           example_ip_mask:Example IP block mask (uint)
parm:           mock_bapm:Mock BAPM parameter (int)
parm:           test_deep_color:Test deep color parameter (int)
parm:           dummy_vm_size:Dummy VM size parameter (uint)
parm:           fake_vm_fragment:Fake VM fragment parameter (uint)
parm:           sample_vm_block:Sample VM block parameter (uint)
parm:           example_vm_fault:Example VM fault parameter (int)
parm:           mock_vm_debug:Mock VM debug parameter (int)
parm:           test_vm_update:Test VM update parameter (int)
parm:           dummy_exp_hw:Dummy experimental HW parameter (int)
parm:           fake_dc:Fake display core parameter (int)
parm:           sample_sched_jobs:Sample scheduler jobs parameter (int)
parm:           example_sched_hw:Example scheduler HW parameter (int)
parm:           mock_ppfeaturemask:Mock power feature mask (uint)
parm:           test_longtraining:Test long training parameter (bool)
parm:           dummy_pcie_gen2:Dummy PCIe gen2 parameter (int)
parm:           fake_mst:Fake MST parameter (int)
parm:           sample_mcbp:Sample MCBP parameter (int)
parm:           example_disable_cu:Example disable CU parameter (charp)
parm:           mock_sched_policy:Mock scheduler policy (int)
parm:           test_hws_max_proc:Test HWS max processes (int)
parm:           dummy_cwsr_enable:Dummy CWSR enable parameter (int)
parm:           fake_max_queues:Fake max queues parameter (int)
parm:           sample_send_sigterm:Sample send sigterm parameter (int)
parm:           example_debug_largebar:Example debug largebar parameter (int)
parm:           mock_ignore_crat:Mock ignore CRAT parameter (int)
parm:           test_halt_hws_hang:Test halt HWS hang parameter (int)
parm:           dummy_hws_gws:Dummy HWS GWS parameter (bool)
parm:           fake_queue_preempt_timeout:Fake queue preemption timeout (int)
parm:           sample_dcfeaturemask:Sample DC feature mask (uint)
parm:           example_dcdebugmask:Example DC debug mask (uint)
parm:           mock_abmlevel:Mock ABM level (uint)
parm:           test_tmz:Test TMZ parameter (int)
parm:           dummy_reset_method:Dummy reset method (int)
parm:           fake_bad_page_threshold:Fake bad page threshold (int)
parm:           sample_num_kcq:Sample number of KCQ (int)
"""


@pytest.fixture
def linux_collector(system_info, conn_mock):
    system_info.os_family = OSFamily.LINUX
    return KernelModuleCollector(system_info, conn_mock)


@pytest.fixture
def win_collector(system_info, conn_mock):
    system_info.os_family = OSFamily.WINDOWS
    return KernelModuleCollector(system_info, conn_mock)


def make_artifact(cmd, exit_code, stdout):
    return SimpleNamespace(command=cmd, exit_code=exit_code, stdout=stdout, stderr="")


def test_parse_proc_modules_empty(linux_collector):
    assert linux_collector.parse_proc_modules("") == {}


def test_parse_proc_modules_basic(linux_collector):
    out = "modA 16384 0 - Live 0x00000000\nmodB 32768 1 - Live 0x00001000"
    parsed = linux_collector.parse_proc_modules(out)
    assert set(parsed) == {"modA", "modB"}
    for v in parsed.values():
        assert v == {"parameters": {}}


def test_get_module_parameters_no_params(linux_collector):
    linux_collector._run_sut_cmd = lambda cmd: make_artifact(cmd, 1, "")
    params = linux_collector.get_module_parameters("modA")
    assert params == {}


def test_get_module_parameters_with_params(linux_collector):
    seq = [
        make_artifact("ls /sys/module/modA/parameters", 0, "p1\np2"),
        make_artifact("cat /sys/module/modA/parameters/p1", 0, "val1\n"),
        make_artifact("cat /sys/module/modA/parameters/p2", 1, ""),
    ]
    linux_collector._run_sut_cmd = lambda cmd, seq=seq: seq.pop(0)
    params = linux_collector.get_module_parameters("modA")
    assert params == {"p1": "val1", "p2": "<unreadable>"}


def test_collect_all_module_info_success(linux_collector):
    seq = [
        make_artifact("cat /proc/modules", 0, "modX 0 0 - Live\n"),
        make_artifact("ls /sys/module/modX/parameters", 0, ""),
    ]
    linux_collector._run_sut_cmd = lambda cmd, seq=seq: seq.pop(0)
    modules = linux_collector.collect_all_module_info()
    assert modules == {"modX": {"parameters": {}}}


def test_collect_data_linux_success(linux_collector):
    seq = [
        make_artifact("cat /proc/modules", 0, "m1 0 0 - Live\n"),
        make_artifact("ls /sys/module/m1/parameters", 1, ""),
        make_artifact("modinfo amdgpu", 1, ""),
    ]
    linux_collector._run_sut_cmd = lambda cmd, seq=seq: seq.pop(0)

    result, data = linux_collector.collect_data()

    assert result.status == ExecutionStatus.OK
    assert isinstance(data, KernelModuleDataModel)
    evt = [e for e in result.events if e.category == "KERNEL_READ"][-1]
    assert evt.priority == EventPriority.INFO.value
    assert "1 kernel modules collected" in result.message
    assert data.kernel_modules == {"m1": {"parameters": {}}}
    assert data.amdgpu_modinfo is None


def test_collect_data_linux_error(linux_collector):
    def bad(cmd):
        return make_artifact(cmd, 1, "")

    linux_collector._run_sut_cmd = bad

    result, data = linux_collector.collect_data()
    assert result.status == ExecutionStatus.ERROR
    assert data is None
    evt = result.events[0]
    assert evt.category == EventCategory.RUNTIME.value or evt.category == EventCategory.OS.value
    assert "Failed to read /proc/modules" in evt.description


def test_collect_data_windows_success(win_collector):
    win_collector._run_sut_cmd = lambda cmd: make_artifact(
        "wmic os get Version /Value", 0, "Version=10.0.19041\r\n"
    )
    result, data = win_collector.collect_data()
    assert result.status == ExecutionStatus.OK
    assert isinstance(data, KernelModuleDataModel)
    assert data.kernel_modules == {"10.0.19041": {"parameters": {}}}
    assert result.message == "1 kernel modules collected"


def test_collect_data_windows_not_found(win_collector):
    win_collector._run_sut_cmd = lambda cmd: make_artifact("wmic os get", 0, "")
    result, data = win_collector.collect_data()
    assert result.status == ExecutionStatus.ERROR
    assert data is None


def test_parse_modinfo_empty(linux_collector):
    """Test parsing of empty modinfo output."""
    result = linux_collector._parse_modinfo("")
    assert result is None


def test_parse_modinfo_basic(linux_collector):
    """Test parsing of basic modinfo output."""
    modinfo_output = """filename:       /lib/modules/1.0.0-test/extra/amdgpu_dummy.ko.xz
version:        10.20.30
license:        GPL and additional rights
description:    AMD GPU Test Module
author:         Test Developer
srcversion:     ABC123DEF456TEST789
depends:        test_dep1,test_dep2,test_dep3
name:           amdgpu
vermagic:       1.0.0-test SMP mod_unload modversions
sig_id:         TEST#1
signer:         test_signer
"""
    result = linux_collector._parse_modinfo(modinfo_output)

    assert result is not None
    assert isinstance(result, ModuleInfo)
    assert result.filename == "/lib/modules/1.0.0-test/extra/amdgpu_dummy.ko.xz"
    assert result.version == "10.20.30"
    assert result.license == "GPL and additional rights"
    assert result.description == "AMD GPU Test Module"
    assert result.author == ["Test Developer"]
    assert result.srcversion == "ABC123DEF456TEST789"
    assert result.depends == ["test_dep1", "test_dep2", "test_dep3"]
    assert result.name == "amdgpu"
    assert result.vermagic == "1.0.0-test SMP mod_unload modversions"
    assert result.sig_id == "TEST#1"
    assert result.signer == "test_signer"


def test_parse_modinfo_with_parameters(linux_collector):
    """Test parsing of modinfo output with parameters."""
    modinfo_output = """filename:       /lib/modules/amdgpu_test.ko
name:           amdgpu
parm:           test_limit:Test limit parameter description (int)
parm:           dummy_size:Dummy size parameter description (uint)
parm:           fake_enable:Fake enable parameter description (int)
"""
    result = linux_collector._parse_modinfo(modinfo_output)

    assert result is not None
    assert len(result.parm) == 3

    assert result.parm[0].name == "test_limit"
    assert result.parm[0].type == "int"
    assert result.parm[0].description == "Test limit parameter description"

    assert result.parm[1].name == "dummy_size"
    assert result.parm[1].type == "uint"
    assert result.parm[1].description == "Dummy size parameter description"

    assert result.parm[2].name == "fake_enable"
    assert result.parm[2].type == "int"
    assert result.parm[2].description == "Fake enable parameter description"


def test_parse_modinfo_with_firmware(linux_collector):
    """Test parsing of modinfo output with firmware entries."""
    modinfo_output = """filename:       /lib/modules/amdgpu_test.ko
name:           amdgpu
firmware:       amdgpu/test_firmware_v1.bin
firmware:       amdgpu/dummy_firmware_v2.bin
firmware:       amdgpu/fake_firmware_v3.bin
"""
    result = linux_collector._parse_modinfo(modinfo_output)

    assert result is not None
    assert len(result.firmware) == 3
    assert "amdgpu/test_firmware_v1.bin" in result.firmware
    assert "amdgpu/dummy_firmware_v2.bin" in result.firmware
    assert "amdgpu/fake_firmware_v3.bin" in result.firmware


def test_parse_modinfo_multiple_authors(linux_collector):
    """Test parsing of modinfo output with multiple authors."""
    modinfo_output = """filename:       /lib/modules/test.ko
author:         Test Author One
author:         Test Author Two
author:         Test Author Three
"""
    result = linux_collector._parse_modinfo(modinfo_output)

    assert result is not None
    assert len(result.author) == 3
    assert result.author == ["Test Author One", "Test Author Two", "Test Author Three"]


def test_collect_data_with_modinfo(linux_collector):
    """Test collect_data includes parsed modinfo data."""
    modinfo_output = """filename:       /lib/modules/amdgpu_test.ko
version:        1.2.3
name:           amdgpu
"""

    seq = [
        make_artifact("cat /proc/modules", 0, "m1 0 0 - Live\n"),
        make_artifact("ls /sys/module/m1/parameters", 1, ""),
        make_artifact("modinfo amdgpu", 0, modinfo_output),
    ]
    linux_collector._run_sut_cmd = lambda cmd, seq=seq: seq.pop(0)

    result, data = linux_collector.collect_data()

    assert result.status == ExecutionStatus.OK
    assert isinstance(data, KernelModuleDataModel)
    assert data.amdgpu_modinfo is not None
    assert data.amdgpu_modinfo.version == "1.2.3"
    assert data.amdgpu_modinfo.name == "amdgpu"
    assert len(result.artifacts) == 1
    assert result.artifacts[0].filename == "modinfo_amdgpu.txt"


def test_collect_data_modinfo_not_available(linux_collector):
    """Test collect_data when modinfo amdgpu fails."""
    seq = [
        make_artifact("cat /proc/modules", 0, "m1 0 0 - Live\n"),
        make_artifact("ls /sys/module/m1/parameters", 1, ""),
        make_artifact("modinfo amdgpu", 1, ""),
    ]
    linux_collector._run_sut_cmd = lambda cmd, seq=seq: seq.pop(0)

    result, data = linux_collector.collect_data()

    assert result.status == ExecutionStatus.OK
    assert isinstance(data, KernelModuleDataModel)
    assert data.amdgpu_modinfo is None
    assert len(result.artifacts) == 0
    warning_events = [e for e in result.events if e.priority == EventPriority.WARNING.value]
    assert len(warning_events) > 0
    assert any("Could not collect modinfo amdgpu" in e.description for e in warning_events)


def test_parse_modinfo_comprehensive(linux_collector, modinfo_amdgpu_full):
    """Test parsing of comprehensive dummy modinfo amdgpu output."""
    result = linux_collector._parse_modinfo(modinfo_amdgpu_full)

    assert result is not None
    assert isinstance(result, ModuleInfo)

    assert result.filename == "/lib/modules/1.2.3-test-kernel/extra/amdgpu_test.ko.xz"
    assert result.version == "99.88.77"
    assert result.license == "GPL and additional rights"
    assert result.description == "AMD GPU Test Module"
    assert result.author == ["Test Author One"]
    assert result.srcversion == "ABCD1234567890TESTVER"

    assert len(result.firmware) == 12
    assert "amdgpu/test_gpu_info_v1.bin" in result.firmware
    assert "amdgpu/dummy_gpu_info_a.bin" in result.firmware
    assert "amdgpu/fake_gpu_info_i.bin" in result.firmware

    expected_depends = [
        "dummy_dep1",
        "dummy_dep2",
        "test_dep3",
        "fake_dep4",
        "sample_dep5",
        "example_dep6",
        "mock_dep7",
    ]
    assert result.depends == expected_depends

    assert result.name == "amdgpu"
    assert result.vermagic == "1.2.3-test-kernel SMP mod_unload modversions"
    assert result.sig_id == "TEST#99"
    assert result.signer == "Test Signing Authority (dummy key 1)"
    assert result.sig_key == "00:11:22:33:44:55:66:77:88:99:AA:BB:CC:DD:EE:FF:00:11:22:33"
    assert result.sig_hashalgo == "test256"

    assert len(result.parm) == 53

    test_param1 = next((p for p in result.parm if p.name == "test_param1"), None)
    assert test_param1 is not None
    assert test_param1.type == "int"
    assert test_param1.description == "Test parameter description one"

    test_dpm = next((p for p in result.parm if p.name == "test_dpm"), None)
    assert test_dpm is not None
    assert test_dpm.type == "int"
    assert test_dpm.description == "Test DPM parameter"

    test_longtraining = next((p for p in result.parm if p.name == "test_longtraining"), None)
    assert test_longtraining is not None
    assert test_longtraining.type == "bool"
    assert "Test long training" in test_longtraining.description

    example_disable_cu = next((p for p in result.parm if p.name == "example_disable_cu"), None)
    assert example_disable_cu is not None
    assert example_disable_cu.type == "charp"
    assert "Example disable CU" in example_disable_cu.description


def test_collect_data_with_full_modinfo(linux_collector, modinfo_amdgpu_full):
    """Test collect_data with comprehensive dummy modinfo data."""
    seq = [
        make_artifact("cat /proc/modules", 0, "amdgpu 16384 0 - Live\n"),
        make_artifact("ls /sys/module/amdgpu/parameters", 1, ""),
        make_artifact("modinfo amdgpu", 0, modinfo_amdgpu_full),
    ]
    linux_collector._run_sut_cmd = lambda cmd, seq=seq: seq.pop(0)

    result, data = linux_collector.collect_data()

    assert result.status == ExecutionStatus.OK
    assert isinstance(data, KernelModuleDataModel)
    assert data.amdgpu_modinfo is not None
    assert data.amdgpu_modinfo.version == "99.88.77"
    assert data.amdgpu_modinfo.name == "amdgpu"
    assert len(data.amdgpu_modinfo.firmware) == 12
    assert len(data.amdgpu_modinfo.parm) == 53
    assert len(data.amdgpu_modinfo.depends) == 7
    assert len(result.artifacts) == 1
    assert result.artifacts[0].filename == "modinfo_amdgpu.txt"
    assert result.artifacts[0].contents == modinfo_amdgpu_full
