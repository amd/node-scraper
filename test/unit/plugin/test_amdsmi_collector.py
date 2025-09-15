import types

import pytest
from pydantic import BaseModel

import nodescraper.plugins.inband.amdsmi.amdsmi_collector as mod
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.plugins.inband.amdsmi.amdsmi_collector import AmdSmiCollector


@pytest.fixture
def collector(system_info, conn_mock):
    c = AmdSmiCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )
    c._events = []

    def _log_event(**kwargs):
        c._events.append(kwargs)

    c._log_event = _log_event
    c.result = types.SimpleNamespace(status=None)
    c.logger = types.SimpleNamespace(
        log=lambda *a, **k: None,
        warning=lambda *a, **k: None,
        info=lambda *a, **k: None,
        error=lambda *a, **k: None,
    )

    return c


class FakeAmdSmiException(Exception):
    """Stand-in for amdsmi.AmdSmiException."""


def set_handles(monkeypatch, handles):
    monkeypatch.setattr(mod, "amdsmi_get_processor_handles", lambda: handles)


def test_get_handles_success(monkeypatch, collector):
    handles = ["h0", "h1"]
    set_handles(monkeypatch, handles)
    assert collector._get_handles() == handles
    assert collector._events == []


def test_get_amdsmi_version(monkeypatch, collector):
    monkeypatch.setattr(mod, "amdsmi_get_lib_version", lambda: "25.3.0")
    monkeypatch.setattr(mod, "amdsmi_get_rocm_version", lambda: "6.4.0")
    v = collector._get_amdsmi_version()
    assert v is not None
    assert v.version == "25.3.0"
    assert v.rocm_version == "6.4.0"


def test_get_gpu_list_with_compute_partition(monkeypatch, collector):
    handles = ["h0", "h1"]
    set_handles(monkeypatch, handles)
    monkeypatch.setattr(mod, "AmdSmiException", FakeAmdSmiException)

    calls = {
        "bdf": {"h0": "0000:01:00.0", "h1": "0001:01:00.0"},
        "uuid": {"h0": "U0", "h1": "U1"},
        "kfd": {"h0": {"kfd_id": "7", "node_id": 3}, "h1": {}},
        "cp": {"h0": {"partition_id": "2"}, "h1": {"partition_id": 0}},
        "mp": {"h0": {}, "h1": {}},
    }

    monkeypatch.setattr(mod, "amdsmi_get_gpu_device_bdf", lambda h: calls["bdf"][h])
    monkeypatch.setattr(mod, "amdsmi_get_gpu_device_uuid", lambda h: calls["uuid"][h])
    monkeypatch.setattr(mod, "amdsmi_get_gpu_kfd_info", lambda h: calls["kfd"][h])
    monkeypatch.setattr(mod, "amdsmi_get_gpu_compute_partition", lambda h: calls["cp"][h])
    monkeypatch.setattr(mod, "amdsmi_get_gpu_memory_partition", lambda h: calls["mp"][h])

    out = collector.get_gpu_list()
    assert out == [
        {
            "gpu": 0,
            "bdf": "0000:01:00.0",
            "uuid": "U0",
            "kfd_id": 7,
            "node_id": 3,
            "partition_id": 2,
        },
        {
            "gpu": 1,
            "bdf": "0001:01:00.0",
            "uuid": "U1",
            "kfd_id": 0,
            "node_id": 0,
            "partition_id": 0,
        },
    ]


def test_get_gpu_list_fallback_to_memory_partition(monkeypatch, collector):
    handles = ["h0"]
    set_handles(monkeypatch, handles)
    monkeypatch.setattr(mod, "AmdSmiException", FakeAmdSmiException)

    monkeypatch.setattr(mod, "amdsmi_get_gpu_device_bdf", lambda h: "0000:01:00.0")
    monkeypatch.setattr(mod, "amdsmi_get_gpu_device_uuid", lambda h: "U0")
    monkeypatch.setattr(mod, "amdsmi_get_gpu_kfd_info", lambda h: {"kfd_id": 1, "node_id": "9"})

    def raise_cp(h):
        raise FakeAmdSmiException(2)

    monkeypatch.setattr(mod, "amdsmi_get_gpu_compute_partition", raise_cp)
    monkeypatch.setattr(
        mod, "amdsmi_get_gpu_memory_partition", lambda h: {"current_partition_id": "4"}
    )

    out = collector.get_gpu_list()
    assert out[0]["partition_id"] == 4


def test_get_process_mixed(monkeypatch, collector):
    handles = ["h0"]
    set_handles(monkeypatch, handles)
    monkeypatch.setattr(mod, "amdsmi_get_gpu_process_list", lambda h: [111, 222])

    def get_info(h, pid):
        if pid == 111:
            return {"name": "proc111", "vram_mem": 42, "gtt_mem": 1, "cpu_mem": 2}
        raise FakeAmdSmiException(2)

    monkeypatch.setattr(mod, "amdsmi_get_gpu_compute_process_info", get_info)
    monkeypatch.setattr(mod, "AmdSmiException", FakeAmdSmiException)

    out = collector.get_process()
    assert out and out[0]["gpu"] == 0
    plist = out[0]["process_list"]
    assert plist[0]["process_info"]["name"] == "proc111"
    assert plist[1]["process_info"] == "222"


def test_get_partition(monkeypatch, collector):
    handles = ["h0", "h1"]
    set_handles(monkeypatch, handles)
    monkeypatch.setattr(mod, "AmdSmiException", FakeAmdSmiException)

    monkeypatch.setattr(
        mod, "amdsmi_get_gpu_compute_partition", lambda h: {"memory": "X", "partition_id": 1}
    )
    monkeypatch.setattr(
        mod,
        "amdsmi_get_gpu_memory_partition",
        lambda h: {"current_partition_id": 1, "memory_partition_caps": [1, 2]},
    )

    out = collector.get_partition()
    assert "current_partition" in out and len(out["current_partition"]) == 2
    assert "memory_partition" in out and len(out["memory_partition"]) == 2


def test_get_firmware_various_shapes(monkeypatch, collector):
    handles = ["h0", "h1", "h2"]
    set_handles(monkeypatch, handles)
    monkeypatch.setattr(mod, "AmdSmiException", FakeAmdSmiException)

    fw_map = {
        "h0": [{"fw_id": "SMU", "fw_version": "1.2.3"}, {"fw_name": "VBIOS", "version": "abc"}],
        "h1": {"fw_list": [{"name": "PMFW", "ver": "9.9"}]},
        "h2": {"SMU": "4.5.6", "XGMI": "7.8.9"},
    }
    monkeypatch.setattr(mod, "amdsmi_get_fw_info", lambda h: fw_map[h])

    out = collector.get_firmware()
    assert out and len(out) == 3
    assert out[0]["fw_list"][0] == {"fw_id": "SMU", "fw_version": "1.2.3"}
    assert out[0]["fw_list"][1] == {"fw_id": "VBIOS", "fw_version": "abc"}
    assert out[1]["fw_list"][0]["fw_id"] in ("PMFW", "name", "")
    ids = {e["fw_id"] for e in out[2]["fw_list"]}
    assert {"SMU", "XGMI"}.issubset(ids)


def test_smi_try_not_supported(monkeypatch, collector):
    monkeypatch.setattr(mod, "AmdSmiException", FakeAmdSmiException)

    def fn():
        raise FakeAmdSmiException(2)

    ret = collector._smi_try(fn, default="X")
    assert ret == "X"
    assert any("not supported" in e["description"] for e in collector._events)


def test_collect_data(monkeypatch, collector):
    init_called = []
    shut_called = []

    monkeypatch.setattr(mod, "amdsmi_init", lambda *a, **k: init_called.append(True))
    monkeypatch.setattr(mod, "amdsmi_shut_down", lambda *a, **k: shut_called.append(True))
    monkeypatch.setattr(AmdSmiCollector, "_get_amdsmi_data", lambda self: {"ok": True})

    res, data = collector.collect_data()
    assert data == {"ok": True}
    assert init_called and shut_called


def test_build_amdsmi_sub_data(collector):
    class M(BaseModel):
        a: int

    out = collector.build_amdsmi_sub_data(M, [{"a": 1}, {"a": 2}])
    assert [m.a for m in out] == [1, 2]

    out2 = collector.build_amdsmi_sub_data(M, {"a": 5})
    assert out2.a == 5

    out3 = collector.build_amdsmi_sub_data(M, ["not-a-dict"])
    assert out3 is None
    assert any(
        "Invalid data type for amd-smi sub data" in e["description"] for e in collector._events
    )
