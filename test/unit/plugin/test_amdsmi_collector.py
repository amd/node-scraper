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
import io
import json
import tarfile
from typing import Any
from unittest.mock import MagicMock

import pytest

from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.plugins.inband.amdsmi.amdsmi_collector import AmdSmiCollector
from nodescraper.plugins.inband.amdsmi.amdsmidata import (
    AmdSmiDataModel,
)
from nodescraper.plugins.inband.amdsmi.collector_args import AmdSmiCollectorArgs


def test_collector_args_instantiation():
    """Test AmdSmiCollectorArgs can be instantiated with and without cper_file_path"""
    args1 = AmdSmiCollectorArgs()
    assert args1.cper_file_path is None

    args2 = AmdSmiCollectorArgs(cper_file_path="/path/to/test.cper")
    assert args2.cper_file_path == "/path/to/test.cper"

    args3 = AmdSmiCollectorArgs(**{"cper_file_path": "/another/path.cper"})
    assert args3.cper_file_path == "/another/path.cper"


def test_data_model_cper_afids_field():
    """Test AmdSmiDataModel accepts cper_afids dict field"""
    data1 = AmdSmiDataModel(cper_afids={"file1.cper": 12345, "file2.cper": 67890})
    assert data1.cper_afids == {"file1.cper": 12345, "file2.cper": 67890}

    data2 = AmdSmiDataModel()
    assert data2.cper_afids == {}

    data3 = AmdSmiDataModel(**{"cper_afids": {"test.cper": 99999}})
    assert data3.cper_afids == {"test.cper": 99999}


def make_cmd_result(stdout: str, stderr: str = "", exit_code: int = 0) -> MagicMock:
    """Create a mock command result"""
    result = MagicMock()
    result.stdout = stdout
    result.stderr = stderr
    result.exit_code = exit_code
    return result


def make_json_response(data: Any) -> str:
    """Convert data to JSON string"""
    return json.dumps(data)


@pytest.fixture
def mock_commands(monkeypatch):
    """Mock all amd-smi commands with sample data"""

    def mock_run_sut_cmd(cmd: str) -> MagicMock:
        if "which amd-smi" in cmd:
            return make_cmd_result("/usr/bin/amd-smi")

        if "version --json" in cmd:
            return make_cmd_result(
                make_json_response(
                    [{"tool": "amdsmi", "amdsmi_library_version": "1.2.3", "rocm_version": "6.1.0"}]
                )
            )

        if "list --json" in cmd:
            return make_cmd_result(
                make_json_response(
                    [
                        {
                            "gpu": 0,
                            "bdf": "0000:0b:00.0",
                            "uuid": "GPU-UUID-123",
                            "kfd_id": 7,
                            "node_id": 3,
                            "partition_id": 0,
                        }
                    ]
                )
            )

        if "process --json" in cmd:
            return make_cmd_result(
                make_json_response(
                    [
                        {
                            "gpu": 0,
                            "process_list": [
                                {
                                    "name": "python",
                                    "pid": 4242,
                                    "mem": 1024,
                                    "engine_usage": {"gfx": 1000000, "enc": 0},
                                    "memory_usage": {
                                        "gtt_mem": 0,
                                        "cpu_mem": 4096,
                                        "vram_mem": 2048,
                                    },
                                    "cu_occupancy": 12,
                                },
                                {
                                    "name": "test",
                                    "pid": 9999,
                                    "mem": 0,
                                    "engine_usage": {"gfx": 0, "enc": 0},
                                    "memory_usage": {"gtt_mem": 0, "cpu_mem": 0, "vram_mem": 0},
                                    "cu_occupancy": 0,
                                },
                            ],
                        }
                    ]
                )
            )

        if "partition --json" in cmd:
            json_output = (
                make_json_response(
                    [{"gpu": 0, "memory_partition": "NPS1", "compute_partition": "CPX_DISABLED"}]
                )
                + "\n"
                + make_json_response(
                    [{"gpu": 1, "memory_partition": "NPS1", "compute_partition": "CPX_DISABLED"}]
                )
                + "\n"
                + make_json_response(
                    [{"gpu_id": "N/A", "profile_index": "N/A", "partition_id": "0"}]
                )
                + "\n\nLegend:\n  * = Current mode"
            )
            return make_cmd_result(json_output)

        if "firmware --json" in cmd:
            return make_cmd_result(
                make_json_response(
                    [
                        {
                            "gpu": 0,
                            "fw_list": [
                                {"fw_name": "SMU", "fw_version": "55.33"},
                                {"fw_name": "VBIOS", "fw_version": "V1"},
                            ],
                        }
                    ]
                )
            )

        if "static -g all --json" in cmd:
            return make_cmd_result(
                make_json_response(
                    {
                        "gpu_data": [
                            {
                                "gpu": 0,
                                "asic": {
                                    "market_name": "SomeGPU",
                                    "vendor_id": "1002",
                                    "vendor_name": "AMD",
                                    "subvendor_id": "1ABC",
                                    "device_id": "0x1234",
                                    "subsystem_id": "0x5678",
                                    "rev_id": "A1",
                                    "asic_serial": "ASERIAL",
                                    "oam_id": 0,
                                    "num_compute_units": 224,
                                    "target_graphics_version": "GFX940",
                                    "vram_type": "HBM3",
                                    "vram_vendor": "Micron",
                                    "vram_bit_width": 4096,
                                },
                                "board": {
                                    "model_number": "Board-42",
                                    "product_serial": "SN0001",
                                    "fru_id": "FRU-1",
                                    "product_name": "ExampleBoard",
                                    "manufacturer_name": "ACME",
                                },
                                "bus": {
                                    "bdf": "0000:0b:00.0",
                                    "max_pcie_width": 16,
                                    "max_pcie_speed": 16.0,
                                    "pcie_interface_version": "PCIe 5.0",
                                    "slot_type": "PCIe",
                                },
                                "vbios": {
                                    "vbios_name": "vbiosA",
                                    "vbios_build_date": "2024-01-01",
                                    "vbios_part_number": "PN123",
                                    "vbios_version": "V1",
                                },
                                "driver": {"driver_name": "amdgpu", "driver_version": "6.1.0"},
                                "numa": {"node": 3, "affinity": 0},
                                "vram": {
                                    "vram_type": "HBM3",
                                    "vram_vendor": "Micron",
                                    "vram_bit_width": 4096,
                                    "vram_size_mb": 65536,
                                },
                                "cache": {
                                    "cache": [
                                        {
                                            "cache_level": 1,
                                            "max_num_cu_shared": 8,
                                            "num_cache_instance": 32,
                                            "cache_size": 262144,
                                            "cache_properties": "PropertyA, PropertyB; PropertyC",
                                        }
                                    ]
                                },
                                "clock": {"frequency": [500, 1500, 2000], "current": 1},
                                "soc_pstate": {},
                                "xgmi_plpd": {},
                            }
                        ]
                    }
                )
            )

        return make_cmd_result("", f"Unknown command: {cmd}", 1)

    return mock_run_sut_cmd


@pytest.fixture
def collector(mock_commands, conn_mock, system_info, monkeypatch):
    """Create a collector with mocked commands"""
    c = AmdSmiCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )
    monkeypatch.setattr(c, "_run_sut_cmd", mock_commands)
    return c


def test_check_amdsmi_installed(collector):
    """Test that _check_amdsmi_installed works"""
    assert collector._check_amdsmi_installed() is True


def test_check_amdsmi_installed_path_hit_leaves_exe_unchanged(collector, monkeypatch):
    """Test that a PATH hit does not trigger the fallback search"""
    mock_run_sut_cmd = MagicMock(return_value=make_cmd_result("/usr/bin/amd-smi"))
    monkeypatch.setattr(collector, "_run_sut_cmd", mock_run_sut_cmd)

    assert collector._check_amdsmi_installed() is True
    assert collector.AMD_SMI_EXE == "amd-smi"
    mock_run_sut_cmd.assert_called_once_with("which amd-smi")


def test_check_amdsmi_installed_falls_back_to_rocm_path(conn_mock, system_info, monkeypatch):
    """Test that a failed PATH lookup falls back to the known install paths"""
    mock_run_sut_cmd = MagicMock(
        side_effect=[
            make_cmd_result("", "no amd-smi in /usr/bin", 1),
            make_cmd_result("/opt/rocm/bin/amd-smi"),
        ]
    )

    c = AmdSmiCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )
    monkeypatch.setattr(c, "_run_sut_cmd", mock_run_sut_cmd)

    assert c._check_amdsmi_installed() is True
    assert c.AMD_SMI_EXE == "/opt/rocm/bin/amd-smi"
    for path in AmdSmiCollector.AMD_SMI_FALLBACK_PATHS:
        assert path in mock_run_sut_cmd.call_args.args[0]


def test_check_amdsmi_not_installed(conn_mock, system_info, monkeypatch):
    """Test when amd-smi is not installed"""

    def mock_which_fail(cmd: str) -> MagicMock:
        if "which amd-smi" in cmd:
            return make_cmd_result("", "no amd-smi in /usr/bin", 1)
        return make_cmd_result("")

    c = AmdSmiCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )
    monkeypatch.setattr(c, "_run_sut_cmd", mock_which_fail)

    result, data = c.collect_data()
    assert data is None
    assert result.status.name == "NOT_RAN"


def test_collect_data(collector):
    """Test full data collection"""
    result, data = collector.collect_data()
    assert data is not None
    assert data.version is not None
    assert data.version.tool == "amdsmi"
    assert data.version.version == "1.2.3"
    assert data.version.rocm_version == "6.1.0"

    # gpu_list
    assert data.gpu_list is not None and len(data.gpu_list) == 1
    assert data.gpu_list[0].bdf == "0000:0b:00.0"
    assert data.gpu_list[0].uuid == "GPU-UUID-123"
    assert data.gpu_list[0].kfd_id == 7
    assert data.gpu_list[0].node_id == 3

    # processes
    assert data.process is not None and len(data.process) == 1
    assert len(data.process[0].process_list) == 2

    assert data.partition is not None
    assert len(data.partition.memory_partition) >= 1
    assert data.partition.memory_partition[0].partition_type == "NPS1"

    # firmware
    assert data.firmware is not None and len(data.firmware) == 1
    assert len(data.firmware[0].fw_list) == 2

    # static
    assert data.static is not None and len(data.static) == 1
    s = data.static[0]
    assert s.bus is not None and s.bus.max_pcie_speed is not None
    assert float(s.bus.max_pcie_speed.value) == pytest.approx(16.0)
    assert s.bus.pcie_interface_version == "PCIe 5.0"


def test_get_gpu_list(collector):
    """Test GPU list parsing"""
    gpu_list = collector.get_gpu_list()
    assert gpu_list is not None and len(gpu_list) == 1
    assert gpu_list[0].gpu == 0
    assert gpu_list[0].bdf == "0000:0b:00.0"
    assert gpu_list[0].uuid == "GPU-UUID-123"


def test_get_process(collector):
    """Test process list parsing"""
    procs = collector.get_process()
    assert procs is not None and len(procs) == 1
    assert procs[0].gpu == 0
    assert len(procs[0].process_list) == 2

    p0 = procs[0].process_list[0].process_info
    assert p0.name == "python"
    assert p0.pid == 4242
    assert p0.mem_usage is not None and p0.mem_usage.unit == "B"
    assert p0.usage.gfx is not None and p0.usage.gfx.unit == "ns"

    p1 = procs[0].process_list[1].process_info
    assert p1.name == "test"
    assert p1.pid == 9999


def test_get_partition(collector):
    """Test partition parsing with multi-JSON output"""
    p = collector.get_partition()
    assert p is not None
    assert len(p.memory_partition) >= 1
    assert p.memory_partition[0].partition_type == "NPS1"


def test_get_firmware(collector):
    """Test firmware parsing"""
    fw = collector.get_firmware()
    assert fw is not None and len(fw) == 1
    assert fw[0].gpu == 0
    assert len(fw[0].fw_list) == 2
    assert fw[0].fw_list[0].fw_id == "SMU"
    assert fw[0].fw_list[0].fw_version == "55.33"


def test_get_static(collector):
    """Test static data parsing"""
    stat = collector.get_static()
    assert stat is not None and len(stat) == 1
    s = stat[0]

    # ASIC
    assert s.asic.market_name == "SomeGPU"
    assert s.asic.vendor_name == "AMD"
    assert s.asic.num_compute_units == 224

    # Board
    assert s.board.amdsmi_model_number == "Board-42"
    assert s.board.manufacturer_name == "ACME"

    # Bus/PCIe
    assert s.bus.bdf == "0000:0b:00.0"
    assert s.bus.max_pcie_width is not None
    assert s.bus.max_pcie_speed is not None

    # VRAM
    assert s.vram.type == "HBM3"
    assert s.vram.vendor == "Micron"

    # Cache
    assert s.cache_info is not None and len(s.cache_info) == 1
    cache = s.cache_info[0]
    assert cache.cache_level.value == 1
    assert cache.cache_properties

    if s.clock is not None:
        assert isinstance(s.clock, dict)
        if "clk" in s.clock and s.clock["clk"] is not None:
            assert s.clock["clk"].frequency_levels is not None


def test_cache_properties_parsing(collector):
    """Test cache properties string parsing"""
    stat = collector.get_static()
    item = stat[0].cache_info[0]
    assert isinstance(item.cache.value, str) and item.cache.value.startswith("Label_")
    assert item.cache_properties
    assert {"PropertyA", "PropertyB", "PropertyC"}.issubset(set(item.cache_properties))


def test_static_data_without_vbios_defaults_to_none(conn_mock, system_info, monkeypatch):
    """When static JSON has no vbios block, get_static() yields AmdSmiStatic with vbios=None"""

    static_payload = {
        "gpu_data": [
            {
                "gpu": 0,
                "asic": {
                    "market_name": "SomeGPU",
                    "vendor_id": "1002",
                    "vendor_name": "AMD",
                    "subvendor_id": "1ABC",
                    "device_id": "0x1234",
                    "subsystem_id": "0x5678",
                    "rev_id": "A1",
                    "asic_serial": "ASERIAL",
                    "oam_id": 0,
                    "num_compute_units": 224,
                    "target_graphics_version": "GFX940",
                },
                "board": {
                    "model_number": "Board-42",
                    "product_serial": "SN0001",
                    "fru_id": "FRU-1",
                    "product_name": "ExampleBoard",
                    "manufacturer_name": "ACME",
                },
                "bus": {
                    "bdf": "0000:0b:00.0",
                    "max_pcie_width": 16,
                    "max_pcie_speed": 16.0,
                    "pcie_interface_version": "PCIe 5.0",
                    "slot_type": "PCIe",
                },
                "driver": {"driver_name": "amdgpu", "driver_version": "6.1.0"},
                "numa": {"node": 3, "affinity": 0},
                "vram": {
                    "vram_type": "HBM3",
                    "vram_vendor": "Micron",
                    "vram_bit_width": 4096,
                    "vram_size_mb": 65536,
                },
                "cache": {
                    "cache": [
                        {
                            "cache_level": 1,
                            "max_num_cu_shared": 8,
                            "num_cache_instance": 32,
                            "cache_size": 262144,
                            "cache_properties": "PropertyA; PropertyB; PropertyC",
                        }
                    ]
                },
                "clock": {"frequency": [500, 1500, 2000], "current": 1},
                "soc_pstate": {},
                "xgmi_plpd": {},
            }
        ]
    }

    def mock_run_sut_cmd(cmd: str) -> MagicMock:
        if "which amd-smi" in cmd:
            return make_cmd_result("/usr/bin/amd-smi")
        if "static -g all --json" in cmd:
            return make_cmd_result(make_json_response(static_payload))
        return make_cmd_result("")

    c = AmdSmiCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )
    monkeypatch.setattr(c, "_run_sut_cmd", mock_run_sut_cmd)

    stat = c.get_static()
    assert stat is not None and len(stat) == 1
    assert stat[0].vbios is None


def test_json_parse_error(conn_mock, system_info, monkeypatch):
    """Test handling of malformed JSON"""

    def mock_bad_json(cmd: str) -> MagicMock:
        if "which amd-smi" in cmd:
            return make_cmd_result("/usr/bin/amd-smi")
        if "version --json" in cmd:
            return make_cmd_result("{ invalid json }")
        return make_cmd_result("")

    c = AmdSmiCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )
    monkeypatch.setattr(c, "_run_sut_cmd", mock_bad_json)

    result, data = c.collect_data()
    assert data is not None
    assert data.version is None
    assert len(result.events) > 0


def test_command_error(conn_mock, system_info, monkeypatch):
    """Test handling of command execution errors"""

    def mock_cmd_error(cmd: str) -> MagicMock:
        if "which amd-smi" in cmd:
            return make_cmd_result("/usr/bin/amd-smi")
        return make_cmd_result("", "Command failed", 1)

    c = AmdSmiCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )
    monkeypatch.setattr(c, "_run_sut_cmd", mock_cmd_error)

    result, data = c.collect_data()
    assert data is not None
    assert data.version is None
    assert data.gpu_list == []
    assert len(result.events) > 0


def test_multi_json_parsing(conn_mock, system_info, monkeypatch):
    """Test parsing of multiple JSON objects with trailing text"""

    def mock_multi_json(cmd: str) -> MagicMock:
        if "which amd-smi" in cmd:
            return make_cmd_result("/usr/bin/amd-smi")
        if "test --json" in cmd:
            multi_json = (
                '[{"data": 1}]\n'
                '[{"data": 2}]\n'
                '[{"data": 3}]\n'
                "\n\nLegend:\n  * = Current mode\n"
            )
            return make_cmd_result(multi_json)
        return make_cmd_result("")

    c = AmdSmiCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )
    monkeypatch.setattr(c, "_run_sut_cmd", mock_multi_json)

    result = c._run_amd_smi_dict("test")

    assert result is not None
    assert isinstance(result, list)
    assert len(result) == 3
    assert result[0] == [{"data": 1}]
    assert result[1] == [{"data": 2}]
    assert result[2] == [{"data": 3}]


def test_single_json_parsing(conn_mock, system_info, monkeypatch):
    """Test that single JSON parsing still works"""

    def mock_single_json(cmd: str) -> MagicMock:
        if "which amd-smi" in cmd:
            return make_cmd_result("/usr/bin/amd-smi")
        if "version --json" in cmd:
            return make_cmd_result(make_json_response([{"tool": "amdsmi", "version": "1.0"}]))
        return make_cmd_result("")

    c = AmdSmiCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )
    monkeypatch.setattr(c, "_run_sut_cmd", mock_single_json)

    result = c._run_amd_smi_dict("version")

    assert result is not None
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["tool"] == "amdsmi"


def test_get_cper_afid_success(conn_mock, system_info, monkeypatch):
    """Test successful AFID retrieval from CPER file"""

    def mock_run_sut_cmd(cmd: str) -> MagicMock:
        if "which amd-smi" in cmd:
            return make_cmd_result("/usr/bin/amd-smi")
        if "ras --afid --cper-file" in cmd:
            return make_cmd_result("12345\n")
        return make_cmd_result("")

    c = AmdSmiCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )
    monkeypatch.setattr(c, "_run_sut_cmd", mock_run_sut_cmd)

    afid = c._get_cper_afid("/path/to/test.cper")

    assert afid is not None
    assert afid == 12345


def test_get_cper_afid_invalid_output(conn_mock, system_info, monkeypatch):
    """Test AFID retrieval with invalid/non-integer output"""

    def mock_run_sut_cmd(cmd: str) -> MagicMock:
        if "which amd-smi" in cmd:
            return make_cmd_result("/usr/bin/amd-smi")
        if "ras --afid --cper-file" in cmd:
            return make_cmd_result("not_a_number\n")
        return make_cmd_result("")

    c = AmdSmiCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )
    monkeypatch.setattr(c, "_run_sut_cmd", mock_run_sut_cmd)

    afid = c._get_cper_afid("/path/to/test.cper")

    assert afid is None


def test_get_cper_afid_command_failure(conn_mock, system_info, monkeypatch):
    """Test AFID retrieval when command fails"""

    def mock_run_sut_cmd(cmd: str) -> MagicMock:
        if "which amd-smi" in cmd:
            return make_cmd_result("/usr/bin/amd-smi")
        if "ras --afid --cper-file" in cmd:
            return make_cmd_result("", stderr="Error: file not found", exit_code=1)
        return make_cmd_result("")

    c = AmdSmiCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )
    monkeypatch.setattr(c, "_run_sut_cmd", mock_run_sut_cmd)

    # _run_amd_smi returns None on non-zero exit code
    afid = c._get_cper_afid("/path/to/test.cper")

    assert afid is None


def test_collect_data_with_cper_file(conn_mock, system_info, mock_commands):
    """Test collect_data with cper_file_path argument"""
    c = AmdSmiCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )

    # Add mock for AFID command
    original_mock = mock_commands

    def extended_mock(cmd: str) -> MagicMock:
        if "ras --afid --cper-file" in cmd:
            return make_cmd_result("99999\n")
        return original_mock(cmd)

    c._run_sut_cmd = extended_mock

    args = AmdSmiCollectorArgs(cper_file_path="/path/to/test.cper")
    result, data = c.collect_data(args)

    assert result is not None
    assert data is not None
    assert "/path/to/test.cper" in data.cper_afids
    assert data.cper_afids["/path/to/test.cper"] == 99999


def test_collect_data_without_cper_file(conn_mock, system_info, mock_commands):
    """Test collect_data without cper_file_path argument"""

    c = AmdSmiCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )
    c._run_sut_cmd = mock_commands

    result, data = c.collect_data()

    assert result is not None
    assert data is not None
    assert isinstance(data.cper_afids, dict)


def test_get_cper_data_with_afids(conn_mock, system_info, monkeypatch):
    """Test get_cper_data returns both CPER files and AFIDs"""

    def mock_run_sut_cmd(cmd: str, sudo: bool = False) -> MagicMock:
        if "which amd-smi" in cmd:
            return make_cmd_result("/usr/bin/amd-smi")
        if "ras --cper --folder" in cmd:
            return make_cmd_result("Created test1.cper\nCreated test2.cper\n")
        if "mkdir -p" in cmd or "tar -czf" in cmd:
            return make_cmd_result("")
        if "ras --afid --cper-file" in cmd:
            if "test1.cper" in cmd:
                return make_cmd_result("12345\n")
            elif "test2.cper" in cmd:
                return make_cmd_result("67890\n")
        return make_cmd_result("")

    def mock_read_sut_file(path: str, encoding=None, strip=False, log_artifact=False):
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            for name in ["test1.cper", "test2.cper"]:
                info = tarfile.TarInfo(name=name)
                info.size = len(b"fake cper data")
                tar.addfile(info, io.BytesIO(b"fake cper data"))

        tar_buffer.seek(0)
        mock_artifact = MagicMock()
        mock_artifact.contents = tar_buffer.read()
        return mock_artifact

    c = AmdSmiCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )
    monkeypatch.setattr(c, "_run_sut_cmd", mock_run_sut_cmd)
    monkeypatch.setattr(c, "_read_sut_file", mock_read_sut_file)

    cper_files, cper_afids = c.get_cper_data()

    assert len(cper_files) == 2
    assert cper_files[0].file_name == "test1.cper"
    assert cper_files[1].file_name == "test2.cper"
    assert cper_afids == {"test1.cper": 12345, "test2.cper": 67890}


def test_get_cper_data_no_cper_files(conn_mock, system_info, monkeypatch):
    """Test get_cper_data returns empty lists when no CPER files created"""

    def mock_run_sut_cmd(cmd: str, sudo: bool = False) -> MagicMock:
        if "which amd-smi" in cmd:
            return make_cmd_result("/usr/bin/amd-smi")
        if "ras --cper --folder" in cmd:
            return make_cmd_result("No CPER files created\n")
        if "mkdir -p" in cmd:
            return make_cmd_result("")
        return make_cmd_result("")

    c = AmdSmiCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )
    monkeypatch.setattr(c, "_run_sut_cmd", mock_run_sut_cmd)

    cper_files, cper_afids = c.get_cper_data()

    assert cper_files == []
    assert cper_afids == {}


def test_collect_data_with_both_auto_and_custom_cper(conn_mock, system_info, monkeypatch):
    """Test that both auto-collected and custom CPER AFIDs are stored in cper_afids"""

    def mock_run_sut_cmd(cmd: str, sudo: bool = False) -> MagicMock:
        if "which amd-smi" in cmd:
            return make_cmd_result("/usr/bin/amd-smi")
        if "version --json" in cmd:
            return make_cmd_result(
                make_json_response(
                    [{"tool": "amdsmi", "amdsmi_library_version": "1.2.3", "rocm_version": "6.1.0"}]
                )
            )
        if "list --json" in cmd:
            return make_cmd_result(make_json_response([{"gpu": 0, "bdf": "0000:0b:00.0"}]))
        if "ras --cper --folder" in cmd:
            return make_cmd_result("Created auto1.cper\n")
        if "ras --afid --cper-file" in cmd:
            if "auto1.cper" in cmd:
                return make_cmd_result("11111\n")
            elif "custom.cper" in cmd:
                return make_cmd_result("99999\n")
        if "mkdir -p" in cmd or "tar -czf" in cmd:
            return make_cmd_result("")
        if "static -g all --json" in cmd:
            return make_cmd_result(make_json_response({"gpu_data": []}))
        return make_cmd_result("")

    def mock_read_sut_file(path: str, encoding=None, strip=False, log_artifact=False):
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w:gz") as tar:
            info = tarfile.TarInfo(name="auto1.cper")
            info.size = len(b"auto cper data")
            tar.addfile(info, io.BytesIO(b"auto cper data"))
        tar_buffer.seek(0)
        mock_artifact = MagicMock()
        mock_artifact.contents = tar_buffer.read()
        return mock_artifact

    c = AmdSmiCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )
    monkeypatch.setattr(c, "_run_sut_cmd", mock_run_sut_cmd)
    monkeypatch.setattr(c, "_read_sut_file", mock_read_sut_file)

    args = AmdSmiCollectorArgs(cper_file_path="/home/user/custom.cper")
    result, data = c.collect_data(args)

    assert result is not None
    assert data is not None
    assert "auto1.cper" in data.cper_afids
    assert data.cper_afids["auto1.cper"] == 11111
    assert "/home/user/custom.cper" in data.cper_afids
    assert data.cper_afids["/home/user/custom.cper"] == 99999


def fabric_json_entry(gpu: int) -> dict[str, Any]:
    """Build one `amd-smi fabric --json` entry as emitted by the tool."""
    return {
        "gpu": gpu,
        "fabric": {
            "gpu": gpu,
            "bdf": f"{gpu + 1:04d}:01:00.0",
            "fabric_info": {
                "bdf": f"{gpu + 1:04d}:01:00.1",
                "version": 4294967295,
                "accelerator_id": 7 - gpu,
                "fabric_type": "UALOE",
                "bandwidth": {"value": 0, "unit": "Mb/s"},
                "latency": {"value": 0, "unit": "ns"},
                "ppod_id": "4c8fab1c-fb8b-42aa-92ae-ea17ca953bdb",
                "ppod_size": 72,
                "vpod_id": 0,
                "vpod_size": 0,
                "local_accelerators": "0, 0, 0, 0, 0, 0, 0, 0",
                "local_active_accelerators": ["0, 0, 0, 0, 0, 0, 0, 0"],
                "addr_mode": "UNKNOWN",
                "accel_state": "UNKNOWN",
            },
            "fabric_telemetry": "N/A",
        },
    }


def make_fabric_collector(conn_mock, system_info, monkeypatch, fabric_payload) -> AmdSmiCollector:
    """Create a collector whose only mocked amd-smi command is `fabric`."""

    def mock_run_sut_cmd(cmd: str, sudo: bool = False) -> MagicMock:
        if "which amd-smi" in cmd:
            return make_cmd_result("/usr/bin/amd-smi")
        if "fabric --json" in cmd:
            if fabric_payload is None:
                return make_cmd_result("", "fabric not supported", 1)
            return make_cmd_result(make_json_response(fabric_payload))
        return make_cmd_result("")

    c = AmdSmiCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )
    monkeypatch.setattr(c, "_run_sut_cmd", mock_run_sut_cmd)
    return c


def test_get_fabric(conn_mock, system_info, monkeypatch):
    """Test fabric parsing from the nested {'gpu': n, 'fabric': {...}} output"""
    payload = [fabric_json_entry(0), fabric_json_entry(1)]
    c = make_fabric_collector(conn_mock, system_info, monkeypatch, payload)

    fabric = c.get_fabric()

    assert len(fabric) == 2
    assert [f.gpu for f in fabric] == [0, 1]
    assert fabric[0].bdf == "0001:01:00.0"
    info = fabric[0].fabric_info
    assert info is not None
    assert info.fabric_type == "UALOE"
    assert info.accelerator_id == 7
    assert info.ppod_id == "4c8fab1c-fb8b-42aa-92ae-ea17ca953bdb"
    assert info.ppod_size == 72
    assert info.bandwidth is not None and info.bandwidth.unit == "Mb/s"
    assert info.latency is not None and info.latency.unit == "ns"


def test_get_fabric_drops_fabric_telemetry(conn_mock, system_info, monkeypatch):
    """Test that the large fabric_telemetry payload is not collected"""
    entry = fabric_json_entry(0)
    entry["fabric"]["fabric_telemetry"] = {"links": [{"id": i} for i in range(64)]}
    c = make_fabric_collector(conn_mock, system_info, monkeypatch, [entry])

    fabric = c.get_fabric()

    assert len(fabric) == 1
    assert "fabric_telemetry" not in fabric[0].model_dump()


def test_get_fabric_gpu_data_wrapper(conn_mock, system_info, monkeypatch):
    """Test fabric parsing when output is wrapped in a gpu_data key"""
    payload = {"gpu_data": [fabric_json_entry(0), fabric_json_entry(1), fabric_json_entry(2)]}
    c = make_fabric_collector(conn_mock, system_info, monkeypatch, payload)

    fabric = c.get_fabric()

    assert [f.gpu for f in fabric] == [0, 1, 2]


def test_get_fabric_flat_entry(conn_mock, system_info, monkeypatch):
    """Test fabric parsing when entries are not nested under a fabric key"""
    payload = [fabric_json_entry(0)["fabric"]]
    c = make_fabric_collector(conn_mock, system_info, monkeypatch, payload)

    fabric = c.get_fabric()

    assert len(fabric) == 1
    assert fabric[0].gpu == 0
    assert fabric[0].fabric_info is not None


def test_get_fabric_command_failure(conn_mock, system_info, monkeypatch):
    """Test fabric returns an empty list when amd-smi fabric fails"""
    c = make_fabric_collector(conn_mock, system_info, monkeypatch, None)

    assert c.get_fabric() == []


def test_get_fabric_na_values(conn_mock, system_info, monkeypatch):
    """Test fabric handles N/A values reported by amd-smi"""
    entry = fabric_json_entry(0)
    entry["fabric"]["bdf"] = "N/A"
    entry["fabric"]["fabric_info"] = "N/A"
    c = make_fabric_collector(conn_mock, system_info, monkeypatch, [entry])

    fabric = c.get_fabric()

    assert len(fabric) == 1
    assert fabric[0].bdf is None
    assert fabric[0].fabric_info is None


# NODE


def node_json_entry(include_gtt: bool = True) -> dict[str, Any]:
    """Build one dummy `amd-smi node --json` entry as emitted by the tool."""
    node: dict[str, Any] = {
        "power_management": {"limit": "N/A", "status": "N/A", "threshold": "N/A"},
    }
    if include_gtt:
        node["gtt"] = {"size_gb": 100.0, "size_pages": 1000}
    return {"node": node}


def make_node_collector(conn_mock, system_info, monkeypatch, node_payload) -> AmdSmiCollector:
    """Create a collector whose only mocked amd-smi command is `node`."""

    def mock_run_sut_cmd(cmd: str, sudo: bool = False) -> MagicMock:
        if "which amd-smi" in cmd:
            return make_cmd_result("/usr/bin/amd-smi")
        if "node --json" in cmd:
            if node_payload is None:
                return make_cmd_result("", "node not supported", 1)
            return make_cmd_result(make_json_response(node_payload))
        return make_cmd_result("")

    c = AmdSmiCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )
    monkeypatch.setattr(c, "_run_sut_cmd", mock_run_sut_cmd)
    return c


def test_get_node(conn_mock, system_info, monkeypatch):
    """Test node parsing from the {"node": {...}} array shape."""
    payload = [node_json_entry()]
    c = make_node_collector(conn_mock, system_info, monkeypatch, payload)

    node = c.get_node()

    assert len(node) == 1
    assert node[0].node.gtt.size_gb == 100.0
    assert node[0].node.gtt.size_pages == 1000
    assert node[0].node.power_management.limit is None
    assert node[0].node.power_management.status is None
    assert node[0].node.power_management.threshold is None


def test_get_node_missing_gtt(conn_mock, system_info, monkeypatch):
    """gtt may be entirely absent from a node entry."""
    payload = [node_json_entry(include_gtt=False)]
    c = make_node_collector(conn_mock, system_info, monkeypatch, payload)

    node = c.get_node()

    assert len(node) == 1
    assert node[0].node.gtt is None


def test_get_node_command_failure(conn_mock, system_info, monkeypatch):
    """Test get_node returns an empty list when the command fails."""
    c = make_node_collector(conn_mock, system_info, monkeypatch, None)

    assert c.get_node() == []


# CPU / CORE METRICS


def cpu_metric_json_entry(cpu: int = 0) -> dict[str, Any]:
    """Build one dummy `amd-smi metric --cpu all --json` entry as emitted by the tool."""
    return {
        "cpu": cpu,
        "power_metrics": {
            "socket power": "100.000 W",
            "socket power limit": "200.000 W",
            "socket max power limit": "200.000 W",
        },
        "prochot": {"prochot_status": 0},
        "freq_metrics": {
            "fclkmemclk": {"fclk": "1000 MHz", "mclk": "2000 MHz"},
            "cclkfreqlimit": "2000 MHz",
            "soc_current_active_freq_limit": {"freq": "2000 MHz", "freq_src": "['Example']"},
            "soc_freq_range": {"max_socket_freq": "2000 MHz", "min_socket_freq": "500 MHz"},
        },
        "c0_residency": {"residency": "1 %"},
        "svi_telemetry_all_rails": {"power": "1000 mW"},
        "pwr_eff_mode": {"mode": "0"},
        "metric_version": {"version": 1},
        "metrics_table": {"cpu_family": 1, "cpu_model": 1, "response": "N/A"},
        "socket_energy": {"response": "1000.0 J"},
        "ddr_bandwidth": {
            "response": {
                "ddr_bw_max_bw": "100 Gbps",
                "ddr_bw_utilized_bw": "0 Gbps",
                "ddr_bw_utilized_pct": "0 %",
            }
        },
        "cpu_temp": {"response": "N/A"},
        "xgmi_pstate_range": {"min_pstate": "N/A", "max_pstate": "N/A"},
        "railisofreq_policy": {"value": 0},
        "dfcstate_ctrl": {"value": 1},
        "pc6_enable": {"value": "N/A"},
        "cc6_enable": {"value": "N/A"},
        "tdelta": {"value": "N/A"},
        "enabled_commands": {
            "READ_ENABLED_COMMANDS_BITMASK0": "N/A",
            "READ_ENABLED_COMMANDS_BITMASK1": "N/A",
            "READ_ENABLED_COMMANDS_BITMASK2": "N/A",
            "WRITE_ENABLED_COMMANDS_BITMASK0": "N/A",
            "WRITE_ENABLED_COMMANDS_BITMASK1": "N/A",
            "WRITE_ENABLED_COMMANDS_BITMASK2": "N/A",
        },
        "sdps_limit": {"value": "N/A"},
    }


def core_metric_json_entry(core: int = 0) -> dict[str, Any]:
    """Build a `amd-smi metric --core all --json` entry as emitted by the tool."""
    return {
        "core": core,
        "boost_limit": {"value": 2000},
        "curr_active_freq_core_limit": {"value": "2000 MHz"},
        "core_energy": {"value": "N/A"},
        "ccd_power": {"value": "N/A"},
        "floor_limit": {"value": "N/A"},
        "eff_floor_limit": {"value": "N/A"},
    }


def make_cpu_core_collector(
    conn_mock, system_info, monkeypatch, cpu_payload=None, core_payload=None
) -> AmdSmiCollector:
    """Create a collector with metric --cpu/--core all commands."""

    def mock_run_sut_cmd(cmd: str, sudo: bool = False) -> MagicMock:
        if "which amd-smi" in cmd:
            return make_cmd_result("/usr/bin/amd-smi")
        if "metric --cpu all --json" in cmd:
            if cpu_payload is None:
                return make_cmd_result("", "cpu metrics not supported", 1)
            return make_cmd_result(make_json_response(cpu_payload))
        if "metric --core all --json" in cmd:
            if core_payload is None:
                return make_cmd_result("", "core metrics not supported", 1)
            return make_cmd_result(make_json_response(core_payload))
        return make_cmd_result("")

    c = AmdSmiCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )
    monkeypatch.setattr(c, "_run_sut_cmd", mock_run_sut_cmd)
    return c


def test_get_cpu_metric(conn_mock, system_info, monkeypatch):
    """Test CPU metric parsing from the amd-smi metric --cpu all --json shape."""
    payload = {"cpu_data": [cpu_metric_json_entry()]}
    c = make_cpu_core_collector(conn_mock, system_info, monkeypatch, cpu_payload=payload)

    cpu_metric = c.get_cpu_metric()

    assert len(cpu_metric) == 1
    entry = cpu_metric[0]
    assert entry.cpu == 0
    assert entry.power_metrics.socket_power.value == 100.0
    assert entry.power_metrics.socket_power_limit.unit == "W"
    assert entry.prochot.prochot_status == 0
    assert entry.freq_metrics.fclkmemclk.fclk.value == 1000
    assert entry.ddr_bandwidth.response.ddr_bw_max_bw.value == 100
    assert entry.cpu_temp.response is None
    assert entry.sdps_limit is None
    assert entry.xgmi_pstate_range.min_pstate is None


def test_get_cpu_metric_command_failure(conn_mock, system_info, monkeypatch):
    """Test get_cpu_metric returns an empty list when the command fails."""
    c = make_cpu_core_collector(conn_mock, system_info, monkeypatch, cpu_payload=None)

    assert c.get_cpu_metric() == []


def test_get_core_metric(conn_mock, system_info, monkeypatch):
    """Test core metric parsing from the amd-smi metric --core all --json shape."""
    payload = {"core_data": [core_metric_json_entry(), core_metric_json_entry(core=1)]}
    c = make_cpu_core_collector(conn_mock, system_info, monkeypatch, core_payload=payload)

    core_metric = c.get_core_metric()

    assert [entry.core for entry in core_metric] == [0, 1]
    assert core_metric[0].boost_limit.value == 2000
    assert core_metric[0].curr_active_freq_core_limit.unit == "MHz"
    assert core_metric[0].core_energy is None
    assert core_metric[0].ccd_power is None
    assert core_metric[0].floor_limit is None


def test_get_core_metric_command_failure(conn_mock, system_info, monkeypatch):
    """Test get_core_metric returns an empty list when the command fails."""
    c = make_cpu_core_collector(conn_mock, system_info, monkeypatch, core_payload=None)

    assert c.get_core_metric() == []
