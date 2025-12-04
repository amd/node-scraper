import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.plugins.inband.amdsmi.amdsmi_collector import AmdSmiCollector


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
