import importlib
import sys
import types
from typing import Optional, Tuple

import pytest

from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.plugins.inband.amdsmi.amdsmi_collector import AmdSmiCollector


class _BaseAmdSmiError(Exception):
    def __init__(self, ret_code: int, *args):
        super().__init__(ret_code, *args)
        self.ret_code = ret_code


class AmdSmiLibraryError(_BaseAmdSmiError): ...


class AmdSmiRetryError(_BaseAmdSmiError): ...


class AmdSmiParameterError(_BaseAmdSmiError): ...


class AmdSmiTimeoutError(_BaseAmdSmiError): ...


def make_fake_amdsmi(
    *,
    handles: Optional[Tuple[object, ...]] = None,
    lib_version="1.2.3",
    rocm_version="6.1.0",
    pcie_static=True,
    raise_on_handles=False,
):
    if handles is None:
        handles = (object(),)

    m = types.SimpleNamespace()
    m.AmdSmiException = _BaseAmdSmiError
    m.AmdSmiLibraryException = AmdSmiLibraryError
    m.AmdSmiRetryException = AmdSmiRetryError
    m.AmdSmiParameterException = AmdSmiParameterError
    m.AmdSmiTimeoutException = AmdSmiTimeoutError

    class AmdSmiInitFlags:
        INIT_AMD_GPUS = 1

    m.AmdSmiInitFlags = AmdSmiInitFlags

    class AmdSmiMemoryType:
        VRAM = 0
        VIS_VRAM = 1
        GTT = 2

    m.AmdSmiMemoryType = AmdSmiMemoryType

    def amdsmi_init(_flags):
        return None

    def amdsmi_shut_down():
        return None

    m.amdsmi_init = amdsmi_init
    m.amdsmi_shut_down = amdsmi_shut_down

    m.amdsmi_get_lib_version = lambda: lib_version
    m.amdsmi_get_rocm_version = lambda: rocm_version

    def amdsmi_get_processor_handles():
        if raise_on_handles:
            raise AmdSmiLibraryError(5)
        return list(handles)

    m.amdsmi_get_processor_handles = amdsmi_get_processor_handles

    m.amdsmi_get_gpu_device_bdf = lambda h: "0000:0b:00.0"
    m.amdsmi_get_gpu_device_uuid = lambda h: "GPU-UUID-123"
    m.amdsmi_get_gpu_kfd_info = lambda h: {
        "kfd_id": 7,
        "node_id": 3,
        "cpu_affinity": 0xFF,
        "current_partition_id": 0,
    }
    m.amdsmi_get_gpu_board_info = lambda h: {
        "vbios_name": "vbiosA",
        "vbios_build_date": "2024-01-01",
        "vbios_part_number": "PN123",
        "vbios_version": "V1",
        "model_number": "Board-42",
        "product_serial": "SN0001",
        "fru_id": "FRU-1",
        "product_name": "ExampleBoard",
        "manufacturer_name": "ACME",
    }
    m.amdsmi_get_gpu_asic_info = lambda h: {
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
        "vram_size_bytes": 64 * 1024 * 1024 * 1024,
    }
    m.amdsmi_get_gpu_driver_info = lambda h: {
        "driver_name": "amdgpu",
        "driver_version": "6.1.0",
    }

    if pcie_static:

        def amdsmi_get_pcie_info(h):
            return {
                "pcie_static": {
                    "max_pcie_width": 16,
                    "max_pcie_speed": 16000,
                    "pcie_interface_version": "PCIe 5.0",
                    "slot_type": "PCIe",
                }
            }

        m.amdsmi_get_pcie_info = amdsmi_get_pcie_info

    m.amdsmi_get_gpu_cache_info = lambda h: {
        "cache": [
            {
                "cache_level": 1,
                "max_num_cu_shared": 8,
                "num_cache_instance": 32,
                "cache_size": 256 * 1024,
                "cache_properties": "PropertyA, PropertyB; PropertyC",
            }
        ]
    }

    def amdsmi_get_clk_freq(h, clk_type):
        return {
            "frequency": [500_000_000, 1_500_000_000, 2_000_000_000],
            "current": 1,
        }

    m.amdsmi_get_clk_freq = amdsmi_get_clk_freq

    m.amdsmi_get_gpu_bad_page_info = lambda h: {"page_list": []}

    m.amdsmi_get_gpu_metrics_info = lambda h: {
        "temperature_hotspot": 55,
        "temperature_mem": 50,
        "average_socket_power": 150,
        "current_gfxclk": 1500,
        "current_uclk": 1000,
    }

    m.amdsmi_get_gpu_od_volt_info = lambda h: {
        "curve": {"vc_points": [{"frequency": 1500, "voltage": 850}]}
    }

    m.amdsmi_get_gpu_vram_usage = lambda h: {
        "vram_used": 1024 * 1024 * 1024,
        "vram_total": 64 * 1024 * 1024 * 1024,
    }

    m.amdsmi_get_gpu_memory_total = lambda h, mem_type: 64 * 1024 * 1024 * 1024

    m.amdsmi_get_gpu_total_ecc_count = lambda h: {"correctable_count": 0, "uncorrectable_count": 0}

    m.amdsmi_get_violation_status = lambda h: {
        "acc_counter": 0,
        "acc_prochot_thrm": 0,
        "acc_ppt_pwr": 0,
    }

    m.amdsmi_get_fw_info = lambda h: {
        "fw_list": [
            {"fw_name": "SMU", "fw_version": "55.33"},
            {"fw_name": "VBIOS", "fw_version": "V1"},
        ]
    }

    m.amdsmi_get_gpu_process_list = lambda h: [
        {
            "name": "python",
            "pid": 4242,
            "mem": 1024,
            "engine_usage": {"gfx": 1_000_000, "enc": 0},
            "memory_usage": {"gtt_mem": 0, "cpu_mem": 4096, "vram_mem": 2048},
            "cu_occupancy": 12,
        },
        {
            "name": "N/A",
            "pid": "9999",
            "mem": "0",
            "engine_usage": {"gfx": "0", "enc": "0"},
            "memory_usage": {"gtt_mem": "0", "cpu_mem": "0", "vram_mem": "0"},
            "cu_occupancy": "0",
        },
    ]

    m.amdsmi_get_gpu_memory_partition = lambda h: {"partition_type": "NPS1"}
    m.amdsmi_get_gpu_compute_partition = lambda h: {"partition_type": "CPX_DISABLED"}

    return m


@pytest.fixture
def install_fake_amdsmi(monkeypatch):
    fake = make_fake_amdsmi()
    mod = types.ModuleType("amdsmi")
    for k, v in fake.__dict__.items():
        setattr(mod, k, v)
    monkeypatch.setitem(sys.modules, "amdsmi", mod)
    return mod


@pytest.fixture
def collector(install_fake_amdsmi, conn_mock, system_info):
    c = AmdSmiCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )
    assert c._bind_amdsmi_or_log() is True
    return c


def test_collect_data(collector):
    result, data = collector.collect_data()
    assert data is not None
    assert data.version is not None
    assert data.version.tool == "amdsmi"
    # gpu_list
    assert data.gpu_list is not None and len(data.gpu_list) == 1
    assert data.gpu_list[0].bdf == "0000:0b:00.0"
    assert data.gpu_list[0].uuid == "GPU-UUID-123"
    # processes
    assert data.process is not None and len(data.process) == 1
    assert len(data.process[0].process_list) == 2
    # static
    assert data.static is not None and len(data.static) == 1
    s = data.static[0]
    assert s.bus is not None and s.bus.max_pcie_speed is not None
    assert float(s.bus.max_pcie_speed.value) == pytest.approx(16.0)


def test_bind_failure(monkeypatch, conn_mock, system_info):
    monkeypatch.setattr(
        importlib, "import_module", lambda name: (_ for _ in ()).throw(ImportError("nope"))
    )
    sys.modules.pop("amdsmi", None)

    c = AmdSmiCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )
    result, data = c.collect_data()
    assert data is None
    assert result.status.name == "NOT_RAN"


def test_handles_exception(monkeypatch, collector):
    fake = make_fake_amdsmi(raise_on_handles=True)
    mod = types.ModuleType("amdsmi")
    for k, v in fake.__dict__.items():
        setattr(mod, k, v)
    monkeypatch.setitem(sys.modules, "amdsmi", mod)
    collector._amdsmi = mod

    gl = collector.get_gpu_list()
    assert gl == [] or gl is None

    gp = collector.get_process()
    assert gp == [] or gp is None

    part = collector.get_partition()
    assert part is not None

    fw = collector.get_firmware()
    assert fw == [] or fw is None

    st = collector.get_static()
    assert st == [] or st is None


def test_partition(collector, install_fake_amdsmi):
    amdsmi = install_fake_amdsmi
    amdsmi.amdsmi_get_gpu_memory_partition = lambda h: "NPS2"
    amdsmi.amdsmi_get_gpu_compute_partition = lambda h: "CPX_ENABLED"
    p = collector.get_partition()
    assert p is not None
    assert len(p.memory_partition) == 1 and len(p.compute_partition) == 1
    assert p.memory_partition[0].partition_type == "NPS2"
    assert p.compute_partition[0].partition_type == "CPX_ENABLED"


def test_pcie(collector, install_fake_amdsmi):
    if hasattr(install_fake_amdsmi, "amdsmi_get_pcie_info"):
        delattr(install_fake_amdsmi, "amdsmi_get_pcie_info")
    stat = collector.get_static()
    assert stat is not None and len(stat) == 1
    assert stat[0].bus is not None
    ms = stat[0].bus.max_pcie_speed
    assert ms is None or ms.unit == "GT/s"


def test_cache(collector):
    stat = collector.get_static()
    item = stat[0].cache_info[0]
    assert isinstance(item.cache.value, str) and item.cache.value.startswith("Label_")
    assert item.cache_properties
    assert {"PropertyA", "PropertyB", "PropertyC"}.issubset(set(item.cache_properties))


def test_process_list(collector):
    procs = collector.get_process()
    assert procs and procs[0].process_list
    p0 = procs[0].process_list[0].process_info
    assert p0.pid == 4242
    assert p0.mem is not None and p0.mem.unit == "B"
    assert p0.usage.gfx is not None and p0.usage.gfx.unit == "ns"
    p1 = procs[0].process_list[1].process_info
    assert p1.name == "N/A"
    assert isinstance(p1.pid, int)


def test_smi_try(monkeypatch, install_fake_amdsmi, collector):
    def raise_not_supported(*a, **kw):
        raise AmdSmiLibraryError(2)  # NOT_SUPPORTED

    install_fake_amdsmi.amdsmi_get_gpu_memory_partition = raise_not_supported

    p = collector.get_partition()
    assert p is not None
    assert len(p.memory_partition) == 1
