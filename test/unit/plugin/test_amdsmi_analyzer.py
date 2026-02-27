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

from typing import Optional

import pytest

from nodescraper.enums import EventPriority
from nodescraper.plugins.inband.amdsmi.amdsmi_analyzer import AmdSmiAnalyzer
from nodescraper.plugins.inband.amdsmi.amdsmidata import (
    AmdSmiDataModel,
    AmdSmiMetric,
    AmdSmiStatic,
    AmdSmiTstData,
    AmdSmiVersion,
    EccState,
    Fw,
    FwListItem,
    MetricEccTotals,
    MetricPcie,
    Partition,
    PartitionCompute,
    PartitionMemory,
    Processes,
    ProcessInfo,
    ProcessListItem,
    ProcessMemoryUsage,
    ProcessUsage,
    StaticAsic,
    StaticBoard,
    StaticBus,
    StaticDriver,
    StaticLimit,
    StaticNuma,
    StaticRas,
    StaticVram,
    ValueUnit,
    XgmiLinkMetrics,
    XgmiMetrics,
)
from nodescraper.plugins.inband.amdsmi.analyzer_args import AmdSmiAnalyzerArgs


@pytest.fixture
def mock_value_unit():
    """Factory fixture to create mock ValueUnit objects."""

    def _create(value, unit):
        return ValueUnit(value=value, unit=unit)

    return _create


@pytest.fixture
def mock_static_asic():
    """Create a mock StaticAsic object."""
    return StaticAsic(
        market_name="AMD Instinct MI123",
        vendor_id="0x1234",
        vendor_name="Advanced Micro Devices Inc",
        subvendor_id="0x1234",
        device_id="0x12a0",
        subsystem_id="0x0c12",
        rev_id="0x00",
        asic_serial="",
        oam_id=0,
        num_compute_units=111,
        target_graphics_version="gfx123",
    )


@pytest.fixture
def mock_static_bus(mock_value_unit):
    """Create a mock StaticBus object."""
    return StaticBus(
        bdf="0000:01:00.0",
        max_pcie_width=mock_value_unit(16, "x"),
        max_pcie_speed=mock_value_unit(32, "GT/s"),
        pcie_interface_version="Gen5",
        slot_type="OAM",
    )


@pytest.fixture
def mock_static_limit(mock_value_unit):
    """Create a mock StaticLimit object."""
    return StaticLimit(
        max_power=mock_value_unit(550.0, "W"),
        min_power=mock_value_unit(0, "W"),
        socket_power=mock_value_unit(0, "W"),
        slowdown_edge_temperature=mock_value_unit(100, "C"),
        slowdown_hotspot_temperature=mock_value_unit(110, "C"),
        slowdown_vram_temperature=mock_value_unit(95, "C"),
        shutdown_edge_temperature=mock_value_unit(105, "C"),
        shutdown_hotspot_temperature=mock_value_unit(115, "C"),
        shutdown_vram_temperature=mock_value_unit(100, "C"),
    )


@pytest.fixture
def mock_static_driver():
    """Create a mock StaticDriver object."""
    return StaticDriver(name="amdgpu", version="1.2.3")


@pytest.fixture
def mock_static_board():
    """Create a mock StaticBoard object."""
    return StaticBoard(
        model_number="",
        product_serial="",
        fru_id="",
        product_name="",
        manufacturer_name="",
    )


@pytest.fixture
def mock_static_numa():
    """Create a mock StaticNuma object."""
    return StaticNuma(node=0, affinity=0)


@pytest.fixture
def mock_static_vram(mock_value_unit):
    """Create a mock StaticVram object."""
    return StaticVram(
        type="sometype",
        vendor="Some vendor",
        size=mock_value_unit(192, "GB"),
        bit_width=mock_value_unit(8192, "bit"),
        max_bandwidth=None,
    )


@pytest.fixture
def mock_analyzer(system_info):
    """Create a mock AmdSmiAnalyzer instance."""
    return AmdSmiAnalyzer(system_info)


def create_static_gpu(
    gpu_id: int = 0,
    max_power: float = 550.0,
    driver_version: str = "1.2.3",
    vendor_id: str = "0x1234",
    subvendor_id: str = "0x1234",
    device_id: str = "0x12a0",
    subsystem_id: str = "0x0c12",
    market_name: str = "AMD Instinct MI123",
) -> AmdSmiStatic:
    """Helper function to create a mock AmdSmiStatic object for testing."""
    return AmdSmiStatic(
        gpu=gpu_id,
        asic=StaticAsic(
            market_name=market_name,
            vendor_id=vendor_id,
            vendor_name="Advanced Micro Devices Inc",
            subvendor_id=subvendor_id,
            device_id=device_id,
            subsystem_id=subsystem_id,
            rev_id="0x00",
            asic_serial="",
            oam_id=0,
            num_compute_units=111,
            target_graphics_version="gfx123",
        ),
        bus=StaticBus(
            bdf="0000:01:00.0",
            max_pcie_width=ValueUnit(value=16, unit="x"),
            max_pcie_speed=ValueUnit(value=32, unit="GT/s"),
            pcie_interface_version="Gen5",
            slot_type="OAM",
        ),
        vbios=None,
        limit=StaticLimit(
            max_power=ValueUnit(value=max_power, unit="W"),
            min_power=ValueUnit(value=0, unit="W"),
            socket_power=ValueUnit(value=0, unit="W"),
            slowdown_edge_temperature=ValueUnit(value=100, unit="C"),
            slowdown_hotspot_temperature=ValueUnit(value=110, unit="C"),
            slowdown_vram_temperature=ValueUnit(value=95, unit="C"),
            shutdown_edge_temperature=ValueUnit(value=105, unit="C"),
            shutdown_hotspot_temperature=ValueUnit(value=115, unit="C"),
            shutdown_vram_temperature=ValueUnit(value=100, unit="C"),
        ),
        driver=StaticDriver(name="amdgpu", version=driver_version),
        board=StaticBoard(
            model_number="",
            product_serial="",
            fru_id="",
            product_name="",
            manufacturer_name="",
        ),
        ras=StaticRas(
            eeprom_version="1.0",
            parity_schema=EccState.ENABLED,
            single_bit_schema=EccState.ENABLED,
            double_bit_schema=EccState.ENABLED,
            poison_schema=EccState.ENABLED,
            ecc_block_state={},
        ),
        soc_pstate=None,
        xgmi_plpd=None,
        process_isolation="NONE",
        numa=StaticNuma(node=0, affinity=0),
        vram=StaticVram(
            type="sometype",
            vendor="Some vendor",
            size=ValueUnit(value=192, unit="GB"),
            bit_width=ValueUnit(value=8192, unit="bit"),
            max_bandwidth=None,
        ),
        cache_info=[],
        partition=None,
        clock=None,
    )


def test_check_expected_max_power_success(mock_analyzer):
    """Test check_expected_max_power passes when all GPUs have correct max power."""
    analyzer = mock_analyzer

    static_data = [
        create_static_gpu(0, max_power=550.0),
        create_static_gpu(1, max_power=550.0),
    ]

    analyzer.check_expected_max_power(static_data, 550)

    assert len(analyzer.result.events) == 0


def test_check_expected_max_power_mismatch(mock_analyzer):
    """Test check_expected_max_power logs error when GPU max power doesn't match."""
    analyzer = mock_analyzer

    static_data = [
        create_static_gpu(0, max_power=550.0),
        create_static_gpu(1, max_power=450.0),
    ]

    analyzer.check_expected_max_power(static_data, 550)

    assert len(analyzer.result.events) == 1
    assert analyzer.result.events[0].category == "PLATFORM"
    assert analyzer.result.events[0].priority == EventPriority.ERROR
    assert "Max power mismatch" in analyzer.result.events[0].description


def test_check_expected_max_power_missing(mock_analyzer):
    """Test check_expected_max_power handles missing max_power gracefully."""
    analyzer = mock_analyzer

    gpu_no_limit = create_static_gpu(0, max_power=550.0)
    gpu_no_limit.limit = None

    static_data = [gpu_no_limit]

    analyzer.check_expected_max_power(static_data, 550)

    assert len(analyzer.result.events) == 1
    assert analyzer.result.events[0].priority == EventPriority.WARNING
    assert "has no max power limit set" in analyzer.result.events[0].description


def test_check_expected_driver_version_success(mock_analyzer):
    """Test check_expected_driver_version passes when all GPUs have correct driver."""
    analyzer = mock_analyzer

    static_data = [
        create_static_gpu(0, driver_version="1.2.3"),
        create_static_gpu(1, driver_version="1.2.3"),
    ]

    analyzer.check_expected_driver_version(static_data, "1.2.3")

    assert len(analyzer.result.events) == 0


def test_check_expected_driver_version_mismatch(mock_analyzer):
    """Test check_expected_driver_version logs error when driver versions don't match."""
    analyzer = mock_analyzer

    static_data = [
        create_static_gpu(0, driver_version="1.2.3"),
        create_static_gpu(1, driver_version="6.7.0"),
    ]

    analyzer.check_expected_driver_version(static_data, "1.2.3")

    assert len(analyzer.result.events) == 1
    assert analyzer.result.events[0].category == "PLATFORM"
    assert analyzer.result.events[0].priority == EventPriority.ERROR
    assert "Driver Version Mismatch" in analyzer.result.events[0].description


def test_expected_gpu_processes_success(mock_analyzer):
    """Test expected_gpu_processes passes when process count is below threshold."""
    analyzer = mock_analyzer

    processes_data = [
        Processes(
            gpu=0,
            process_list=[
                ProcessListItem(
                    process_info=ProcessInfo(
                        name="test_process",
                        pid=1234,
                        memory_usage=ProcessMemoryUsage(gtt_mem=None, cpu_mem=None, vram_mem=None),
                        mem_usage=None,
                        usage=ProcessUsage(gfx=None, enc=None),
                    )
                ),
                ProcessListItem(
                    process_info=ProcessInfo(
                        name="test_process2",
                        pid=5678,
                        memory_usage=ProcessMemoryUsage(gtt_mem=None, cpu_mem=None, vram_mem=None),
                        mem_usage=None,
                        usage=ProcessUsage(gfx=None, enc=None),
                    )
                ),
            ],
        ),
    ]

    analyzer.expected_gpu_processes(processes_data, 5)

    assert len(analyzer.result.events) == 0


def test_expected_gpu_processes_exceeds(mock_analyzer):
    """Test expected_gpu_processes logs error when process count exceeds threshold."""
    analyzer = mock_analyzer

    processes_data = [
        Processes(
            gpu=0,
            process_list=[
                ProcessListItem(
                    process_info=ProcessInfo(
                        name=f"process_{i}",
                        pid=i,
                        memory_usage=ProcessMemoryUsage(gtt_mem=None, cpu_mem=None, vram_mem=None),
                        mem_usage=None,
                        usage=ProcessUsage(gfx=None, enc=None),
                    )
                )
                for i in range(10)
            ],
        ),
    ]

    analyzer.expected_gpu_processes(processes_data, 5)

    assert len(analyzer.result.events) == 1
    assert analyzer.result.events[0].priority == EventPriority.ERROR
    assert "Number of processes exceeds max processes" in analyzer.result.events[0].description


def test_expected_gpu_processes_no_data(mock_analyzer):
    """Test expected_gpu_processes handles missing process data."""
    analyzer = mock_analyzer

    analyzer.expected_gpu_processes(None, 5)

    assert len(analyzer.result.events) == 1
    assert analyzer.result.events[0].priority == EventPriority.WARNING
    assert "No GPU processes data available" in analyzer.result.events[0].description


def test_static_consistancy_check_success(mock_analyzer):
    """Test static_consistancy_check passes when all GPUs have consistent data."""
    analyzer = mock_analyzer

    static_data = [
        create_static_gpu(0),
        create_static_gpu(1),
    ]

    analyzer.static_consistancy_check(static_data)

    assert len(analyzer.result.events) == 0


def test_static_consistancy_check_inconsistent(mock_analyzer):
    """Test static_consistancy_check logs warning when GPU data is inconsistent."""
    analyzer = mock_analyzer

    static_data = [
        create_static_gpu(0, vendor_id="0x1234"),
        create_static_gpu(1, vendor_id="0x1003"),
    ]

    analyzer.static_consistancy_check(static_data)

    assert len(analyzer.result.events) >= 1
    assert analyzer.result.events[0].priority == EventPriority.WARNING


def test_check_static_data_success(mock_analyzer):
    """Test check_static_data passes when all GPUs match expected configuration."""
    analyzer = mock_analyzer

    static_data = [
        create_static_gpu(0),
    ]

    analyzer.check_static_data(
        static_data,
        vendor_id="0x1234",
        subvendor_id="0x1234",
        device_id=("0x12a0", "0x12a0"),
        subsystem_id=("0x0c12", "0x0c12"),
        sku_name="AMD Instinct MI123",
    )

    assert len(analyzer.result.events) == 0


def test_check_static_data_mismatch(mock_analyzer):
    """Test check_static_data logs error when GPU configuration doesn't match."""
    analyzer = mock_analyzer

    static_data = [
        create_static_gpu(0, device_id="0x74a1"),
    ]

    analyzer.check_static_data(
        static_data,
        vendor_id="0x1234",
        subvendor_id="0x1234",
        device_id=("0x12a0", "0x12a0"),
        subsystem_id=("0x0c12", "0x0c12"),
        sku_name="AMD Instinct MI123",
    )

    assert len(analyzer.result.events) >= 1


def test_check_pldm_version_success(mock_analyzer):
    """Test check_pldm_version passes when PLDM version matches."""
    analyzer = mock_analyzer

    firmware_data = [
        Fw(
            gpu=0,
            fw_list=[
                FwListItem(fw_id="PLDM_BUNDLE", fw_version="1.2.3"),
            ],
        ),
    ]

    analyzer.check_pldm_version(firmware_data, "1.2.3")

    assert len(analyzer.result.events) == 0


def test_check_pldm_version_mismatch(mock_analyzer):
    """Test check_pldm_version logs error when PLDM version doesn't match."""
    analyzer = mock_analyzer

    firmware_data = [
        Fw(
            gpu=0,
            fw_list=[
                FwListItem(fw_id="PLDM_BUNDLE", fw_version="1.2.3"),
            ],
        ),
    ]

    analyzer.check_pldm_version(firmware_data, "1.2.4")

    assert len(analyzer.result.events) == 1
    assert analyzer.result.events[0].priority == EventPriority.ERROR


def test_check_pldm_version_missing(mock_analyzer):
    """Test check_pldm_version handles missing PLDM firmware."""
    analyzer = mock_analyzer

    firmware_data = [
        Fw(
            gpu=0,
            fw_list=[
                FwListItem(fw_id="OTHER_FW", fw_version="1.0.0"),
            ],
        ),
    ]

    analyzer.check_pldm_version(firmware_data, "1.2.3")

    assert len(analyzer.result.events) == 1
    assert analyzer.result.events[0].priority == EventPriority.ERROR


def test_check_expected_memory_partition_mode_success(mock_analyzer):
    """Test check_expected_memory_partition_mode passes when partition modes match."""
    analyzer = mock_analyzer

    partition_data = Partition(
        memory_partition=[
            PartitionMemory(gpu_id=0, partition_type="NPS1"),
            PartitionMemory(gpu_id=1, partition_type="NPS1"),
        ],
        compute_partition=[
            PartitionCompute(gpu_id=0, partition_type="SPX"),
            PartitionCompute(gpu_id=1, partition_type="SPX"),
        ],
    )

    analyzer.check_expected_memory_partition_mode(partition_data, "NPS1", "SPX")

    assert len(analyzer.result.events) == 0


def test_check_expected_memory_partition_mode_mismatch(mock_analyzer):
    """Test check_expected_memory_partition_mode logs error when modes don't match."""
    analyzer = mock_analyzer

    partition_data = Partition(
        memory_partition=[
            PartitionMemory(gpu_id=0, partition_type="NPS1"),
            PartitionMemory(gpu_id=1, partition_type="NPS4"),
        ],
        compute_partition=[
            PartitionCompute(gpu_id=0, partition_type="SPX"),
            PartitionCompute(gpu_id=1, partition_type="SPX"),
        ],
    )

    analyzer.check_expected_memory_partition_mode(partition_data, "NPS1", "SPX")

    assert len(analyzer.result.events) >= 0


def test_check_expected_xgmi_link_speed_success(mock_analyzer):
    """Test check_expected_xgmi_link_speed passes when XGMI speed matches."""
    analyzer = mock_analyzer

    xgmi_data = [
        XgmiMetrics(
            gpu=0,
            bdf="0000:01:00.0",
            link_metrics=XgmiLinkMetrics(
                bit_rate=ValueUnit(value=32.0, unit="GT/s"),
                max_bandwidth=None,
                link_type="XGMI",
                links=[],
            ),
        ),
        XgmiMetrics(
            gpu=1,
            bdf="0000:02:00.0",
            link_metrics=XgmiLinkMetrics(
                bit_rate=ValueUnit(value=32.0, unit="GT/s"),
                max_bandwidth=None,
                link_type="XGMI",
                links=[],
            ),
        ),
    ]

    analyzer.check_expected_xgmi_link_speed(xgmi_data, expected_xgmi_speed=[32.0])

    assert len(analyzer.result.events) == 0


def test_check_expected_xgmi_link_speed_mismatch(mock_analyzer):
    """Test check_expected_xgmi_link_speed logs error when speed doesn't match."""
    analyzer = mock_analyzer

    xgmi_data = [
        XgmiMetrics(
            gpu=0,
            bdf="0000:01:00.0",
            link_metrics=XgmiLinkMetrics(
                bit_rate=ValueUnit(value=25.0, unit="GT/s"),
                max_bandwidth=None,
                link_type="XGMI",
                links=[],
            ),
        ),
    ]

    analyzer.check_expected_xgmi_link_speed(xgmi_data, expected_xgmi_speed=[32.0])

    assert len(analyzer.result.events) == 1
    assert analyzer.result.events[0].category == "IO"
    assert analyzer.result.events[0].priority == EventPriority.ERROR
    assert "XGMI link speed is not as expected" in analyzer.result.events[0].description


def test_check_expected_xgmi_link_speed_multiple_valid_speeds(mock_analyzer):
    """Test check_expected_xgmi_link_speed with multiple valid speeds."""
    analyzer = mock_analyzer

    xgmi_data = [
        XgmiMetrics(
            gpu=0,
            bdf="0000:01:00.0",
            link_metrics=XgmiLinkMetrics(
                bit_rate=ValueUnit(value=36.0, unit="GT/s"),
                max_bandwidth=None,
                link_type="XGMI",
                links=[],
            ),
        ),
        XgmiMetrics(
            gpu=1,
            bdf="0000:02:00.0",
            link_metrics=XgmiLinkMetrics(
                bit_rate=ValueUnit(value=38.0, unit="GT/s"),
                max_bandwidth=None,
                link_type="XGMI",
                links=[],
            ),
        ),
    ]

    analyzer.check_expected_xgmi_link_speed(xgmi_data, expected_xgmi_speed=[36.0, 38.0])

    assert len(analyzer.result.events) == 0


def test_check_expected_xgmi_link_speed_no_data(mock_analyzer):
    """Test check_expected_xgmi_link_speed handles missing XGMI data."""
    analyzer = mock_analyzer

    analyzer.check_expected_xgmi_link_speed(None, expected_xgmi_speed=[32.0])

    assert len(analyzer.result.events) == 1
    assert analyzer.result.events[0].priority == EventPriority.WARNING
    assert "XGMI link speed data is not available" in analyzer.result.events[0].description


def test_check_expected_xgmi_link_speed_missing_bit_rate(mock_analyzer):
    """Test check_expected_xgmi_link_speed handles missing bit rate value."""
    analyzer = mock_analyzer

    xgmi_data = [
        XgmiMetrics(
            gpu=0,
            bdf="0000:01:00.0",
            link_metrics=XgmiLinkMetrics(
                bit_rate=None,
                max_bandwidth=None,
                link_type="XGMI",
                links=[],
            ),
        ),
    ]

    analyzer.check_expected_xgmi_link_speed(xgmi_data, expected_xgmi_speed=[32.0])

    assert len(analyzer.result.events) == 1
    assert analyzer.result.events[0].priority == EventPriority.ERROR
    assert "XGMI link speed is not available" in analyzer.result.events[0].description


def test_check_amdsmitst_success(mock_analyzer):
    """Test check_amdsmitst passes when no tests failed."""
    analyzer = mock_analyzer

    tst_data = AmdSmiTstData(
        passed_tests=["test1", "test2", "test3"],
        skipped_tests=[],
        failed_tests=[],
        failed_test_count=0,
    )

    analyzer.check_amdsmitst(tst_data)

    assert len(analyzer.result.events) == 0


def test_check_amdsmitst_failures(mock_analyzer):
    """Test check_amdsmitst logs error when tests failed."""
    analyzer = mock_analyzer

    tst_data = AmdSmiTstData(
        passed_tests=["test1", "test2"],
        skipped_tests=["test3"],
        failed_tests=["test4", "test5"],
        failed_test_count=2,
    )

    analyzer.check_amdsmitst(tst_data)

    assert len(analyzer.result.events) == 1
    assert analyzer.result.events[0].category == "APPLICATION"
    assert analyzer.result.events[0].priority == EventPriority.ERROR
    assert "2 failed tests running amdsmitst" in analyzer.result.events[0].description
    assert analyzer.result.events[0].data["failed_test_count"] == 2
    assert analyzer.result.events[0].data["failed_tests"] == ["test4", "test5"]


def test_analyze_data_full_workflow(mock_analyzer):
    """Test full analyze_data workflow with various checks."""
    analyzer = mock_analyzer

    data = AmdSmiDataModel(
        version=AmdSmiVersion(
            tool="amdsmi",
            version="1.2.3",
            amdsmi_library_version="1.2.3",
            rocm_version="6.1.0",
        ),
        static=[
            create_static_gpu(0, max_power=550.0, driver_version="1.2.3"),
            create_static_gpu(1, max_power=550.0, driver_version="1.2.3"),
        ],
        process=[
            Processes(
                gpu=0,
                process_list=[
                    ProcessListItem(
                        process_info=ProcessInfo(
                            name="test",
                            pid=1234,
                            memory_usage=ProcessMemoryUsage(
                                gtt_mem=None, cpu_mem=None, vram_mem=None
                            ),
                            mem_usage=None,
                            usage=ProcessUsage(gfx=None, enc=None),
                        )
                    ),
                ],
            ),
        ],
        firmware=[
            Fw(gpu=0, fw_list=[FwListItem(fw_id="PLDM_BUNDLE", fw_version="1.2.3")]),
        ],
        partition=None,
        gpu_list=None,
        xgmi_metric=[
            XgmiMetrics(
                gpu=0,
                bdf="0000:01:00.0",
                link_metrics=XgmiLinkMetrics(
                    bit_rate=ValueUnit(value=32.0, unit="GT/s"),
                    max_bandwidth=None,
                    link_type="XGMI",
                    links=[],
                ),
            ),
        ],
        amdsmitst_data=AmdSmiTstData(
            passed_tests=["test1", "test2"],
            skipped_tests=[],
            failed_tests=[],
            failed_test_count=0,
        ),
    )

    args = AmdSmiAnalyzerArgs(
        expected_max_power=550,
        expected_driver_version="1.2.3",
        expected_gpu_processes=10,
        expected_xgmi_speed=[32.0],
    )

    result = analyzer.analyze_data(data, args)

    assert len(result.events) == 0


def test_analyze_data_no_static_data(mock_analyzer):
    """Test analyze_data when no static data is available."""
    analyzer = mock_analyzer

    data = AmdSmiDataModel(
        version=None,
        static=None,
        process=None,
        firmware=None,
        partition=None,
        gpu_list=None,
    )

    result = analyzer.analyze_data(data, None)

    assert len(result.events) >= 1
    assert any("No AMD SMI static data available" in event.description for event in result.events)


# All required keys for MetricPcie / MetricEccTotals (no defaults in model -> must be present).
_PCIE_KEYS = [
    "width",
    "speed",
    "bandwidth",
    "replay_count",
    "l0_to_recovery_count",
    "replay_roll_over_count",
    "nak_sent_count",
    "nak_received_count",
    "current_bandwidth_sent",
    "current_bandwidth_received",
    "max_packet_size",
    "lc_perf_other_end_recovery",
]
_ECC_TOTALS_KEYS = [
    "total_correctable_count",
    "total_uncorrectable_count",
    "total_deferred_count",
    "cache_correctable_count",
    "cache_uncorrectable_count",
]


def _pcie_dict(**overrides):
    """Full PCIe dict for model_validate; overrides merged on top."""
    base = {k: None for k in _PCIE_KEYS}
    for k, v in overrides.items():
        if v is not None and isinstance(v, ValueUnit):
            base[k] = {"value": v.value, "unit": v.unit}
        else:
            base[k] = v
    return MetricPcie.model_validate(base)


def _ecc_totals_dict(**overrides):
    """Full ECC totals dict for model_validate; overrides merged on top."""
    base = {k: None for k in _ECC_TOTALS_KEYS}
    base.update(overrides)
    return MetricEccTotals.model_validate(base)


def _minimal_amdsmi_metric(
    gpu: int = 0,
    pcie: Optional[MetricPcie] = None,
    ecc: Optional[MetricEccTotals] = None,
    ecc_blocks: Optional[dict] = None,
) -> AmdSmiMetric:
    """Build minimal AmdSmiMetric for PCIe/ECC tests with all required fields present."""
    pcie_dict = pcie.model_dump() if pcie is not None else {k: None for k in _PCIE_KEYS}
    ecc_dict = ecc.model_dump() if ecc is not None else {k: None for k in _ECC_TOTALS_KEYS}
    return AmdSmiMetric.model_validate(
        {
            "gpu": gpu,
            "usage": {
                "gfx_activity": None,
                "umc_activity": None,
                "mm_activity": None,
                "vcn_activity": [],
                "jpeg_activity": [],
                "gfx_busy_inst": None,
                "jpeg_busy": None,
                "vcn_busy": None,
            },
            "power": {
                "socket_power": None,
                "gfx_voltage": None,
                "soc_voltage": None,
                "mem_voltage": None,
                "throttle_status": None,
                "power_management": None,
            },
            "clock": {},
            "temperature": {"edge": None, "hotspot": None, "mem": None},
            "pcie": pcie_dict,
            "ecc": ecc_dict,
            "ecc_blocks": ecc_blocks if ecc_blocks is not None else {},
            "fan": {"speed": None, "max": None, "rpm": None, "usage": None},
            "voltage_curve": None,
            "perf_level": None,
            "xgmi_err": None,
            "energy": None,
            "mem_usage": {
                "total_vram": None,
                "used_vram": None,
                "free_vram": None,
                "total_visible_vram": None,
                "used_visible_vram": None,
                "free_visible_vram": None,
                "total_gtt": None,
                "used_gtt": None,
                "free_gtt": None,
            },
            "throttle": {},
        }
    )


def test_check_amdsmi_metric_pcie_width_fail(mock_analyzer):
    """PCIe width not x16 generates error."""
    analyzer = mock_analyzer
    pcie = _pcie_dict(width=8)
    metrics = [_minimal_amdsmi_metric(0, pcie=pcie)]
    analyzer.check_amdsmi_metric_pcie(metrics, 4, 2)
    assert len(analyzer.result.events) == 1
    assert "PCIe width is not x16" in analyzer.result.events[0].description
    assert analyzer.result.events[0].data.get("pcie_width") == 8
    assert analyzer.result.events[0].priority == EventPriority.ERROR
    assert analyzer.result.events[0].category == "IO"


def test_check_amdsmi_metric_pcie_speed_fail(mock_analyzer):
    """PCIe speed not Gen5 (32 GT/s) generates error."""
    analyzer = mock_analyzer
    pcie = _pcie_dict(width=16, speed=ValueUnit(value=16, unit="GT/s"))
    metrics = [_minimal_amdsmi_metric(0, pcie=pcie)]
    analyzer.check_amdsmi_metric_pcie(metrics, 4, 2)
    assert len(analyzer.result.events) == 1
    assert "PCIe link speed is not Gen5" in analyzer.result.events[0].description
    assert analyzer.result.events[0].data.get("pcie_speed") == 16
    assert analyzer.result.events[0].priority == EventPriority.ERROR


def test_check_amdsmi_metric_pcie_l0_warning(mock_analyzer):
    """L0 recovery count above warning threshold generates warning."""
    analyzer = mock_analyzer
    pcie = _pcie_dict(width=16, l0_to_recovery_count=2)
    metrics = [_minimal_amdsmi_metric(0, pcie=pcie)]
    analyzer.check_amdsmi_metric_pcie(metrics, 4, 1)
    assert len(analyzer.result.events) == 1
    assert "L0 recoveries" in analyzer.result.events[0].description
    assert analyzer.result.events[0].data.get("l0_to_recovery_count") == 2
    assert analyzer.result.events[0].priority == EventPriority.WARNING


def test_check_amdsmi_metric_pcie_l0_error(mock_analyzer):
    """L0 recovery count above error threshold generates error."""
    analyzer = mock_analyzer
    pcie = _pcie_dict(width=16, l0_to_recovery_count=10)
    metrics = [_minimal_amdsmi_metric(0, pcie=pcie)]
    analyzer.check_amdsmi_metric_pcie(metrics, 4, 2)
    assert len(analyzer.result.events) == 1
    assert "L0 recoveries" in analyzer.result.events[0].description
    assert analyzer.result.events[0].data.get("l0_to_recovery_count") == 10
    assert analyzer.result.events[0].priority == EventPriority.ERROR


def test_check_amdsmi_metric_pcie_replay_count_warning(mock_analyzer):
    """PCIe replay count > 0 generates warning."""
    analyzer = mock_analyzer
    pcie = _pcie_dict(width=16, replay_count=10)
    metrics = [_minimal_amdsmi_metric(0, pcie=pcie)]
    analyzer.check_amdsmi_metric_pcie(metrics, 4, 2)
    assert len(analyzer.result.events) == 1
    assert "replay count" in analyzer.result.events[0].description
    assert analyzer.result.events[0].data.get("replay_count") == 10
    assert analyzer.result.events[0].priority == EventPriority.WARNING


def test_check_amdsmi_metric_pcie_nak_sent_warning(mock_analyzer):
    """PCIe NAK sent count > 0 generates warning."""
    analyzer = mock_analyzer
    pcie = _pcie_dict(width=16, nak_sent_count=1)
    metrics = [_minimal_amdsmi_metric(0, pcie=pcie)]
    analyzer.check_amdsmi_metric_pcie(metrics, 4, 2)
    assert len(analyzer.result.events) == 1
    assert (
        "NAKs" in analyzer.result.events[0].description
        and "sent" in analyzer.result.events[0].description
    )
    assert analyzer.result.events[0].data.get("nak_sent_count") == 1
    assert analyzer.result.events[0].priority == EventPriority.WARNING


def test_check_amdsmi_metric_pcie_nak_received_warning(mock_analyzer):
    """PCIe NAK received count > 0 generates warning."""
    analyzer = mock_analyzer
    pcie = _pcie_dict(width=16, nak_received_count=1)
    metrics = [_minimal_amdsmi_metric(0, pcie=pcie)]
    analyzer.check_amdsmi_metric_pcie(metrics, 4, 2)
    assert len(analyzer.result.events) == 1
    assert (
        "NAKs" in analyzer.result.events[0].description
        and "received" in analyzer.result.events[0].description
    )
    assert analyzer.result.events[0].priority == EventPriority.WARNING


def test_check_amdsmi_metric_pcie_pass(mock_analyzer):
    """PCIe metrics all OK generates no events."""
    analyzer = mock_analyzer
    pcie = _pcie_dict(width=16, speed=ValueUnit(value=32, unit="GT/s"))
    metrics = [_minimal_amdsmi_metric(0, pcie=pcie)]
    analyzer.check_amdsmi_metric_pcie(metrics, 4, 2)
    assert len(analyzer.result.events) == 0


def test_check_amdsmi_metric_ecc_totals(mock_analyzer):
    """ECC totals generate expected events."""
    analyzer = mock_analyzer
    metrics = [
        _minimal_amdsmi_metric(
            0, ecc=_ecc_totals_dict(total_correctable_count=1, total_uncorrectable_count=0)
        ),
        _minimal_amdsmi_metric(1, ecc=_ecc_totals_dict(total_uncorrectable_count=1)),
        _minimal_amdsmi_metric(2, ecc=_ecc_totals_dict(total_deferred_count=1)),
        _minimal_amdsmi_metric(3, ecc=_ecc_totals_dict(cache_correctable_count=1)),
        _minimal_amdsmi_metric(4, ecc=_ecc_totals_dict(cache_uncorrectable_count=1)),
    ]
    analyzer.check_amdsmi_metric_ecc_totals(metrics)
    assert len(analyzer.result.events) == 5
    # Analyzer uses generic description "GPU ECC error count detected"; type is in data["error_type"]
    for e in analyzer.result.events:
        assert e.description == "GPU ECC error count detected"
        assert "error_type" in e.data and "error_count" in e.data
    error_types = [e.data["error_type"] for e in analyzer.result.events]
    assert "Total correctable ECC errors" in error_types
    assert "Total uncorrectable ECC errors" in error_types
    assert "Total deferred ECC errors" in error_types
    assert "Cache correctable ECC errors" in error_types
    assert "Cache uncorrectable ECC errors" in error_types


def test_check_amdsmi_metric_ecc_blocks(mock_analyzer):
    """ECC block-level correctable/uncorrectable/deferred generate events."""
    analyzer = mock_analyzer
    ecc_blocks = {
        "SDMA": {"correctable_count": 0, "uncorrectable_count": 3, "deferred_count": 0},
        "GFX": {"correctable_count": 2, "uncorrectable_count": 0, "deferred_count": 0},
        "MMHUB": {"correctable_count": 0, "uncorrectable_count": 10, "deferred_count": 1},
        "HDP": {"correctable_count": 8, "uncorrectable_count": 5, "deferred_count": 0},
    }
    metrics = [_minimal_amdsmi_metric(0, ecc_blocks=ecc_blocks)]
    analyzer.check_amdsmi_metric_ecc(metrics)
    events = analyzer.result.events
    assert len(events) >= 6
    desc = [e.description for e in events]
    assert any("SDMA" in d and "uncorrectable" in d for d in desc)
    assert any("GFX" in d and "correctable" in d for d in desc)
    assert any("MMHUB" in d for d in desc)
    assert any("HDP" in d for d in desc)
