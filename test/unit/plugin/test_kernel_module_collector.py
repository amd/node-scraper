from types import SimpleNamespace

import pytest

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.plugins.inband.kernel_module.kernel_module_collector import (
    KernelModuleCollector,
)
from nodescraper.plugins.inband.kernel_module.kernel_module_data import (
    KernelModuleDataModel,
)


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
    modules, artifact = linux_collector.collect_all_module_info()
    assert isinstance(artifact, SimpleNamespace)
    assert modules == {"modX": {"parameters": {}}}


def test_collect_all_module_info_failure(linux_collector):
    linux_collector._run_sut_cmd = lambda cmd: make_artifact(cmd, 1, "")
    with pytest.raises(RuntimeError):
        linux_collector.collect_all_module_info()


def test_collect_data_linux_success(linux_collector):
    seq = [
        make_artifact("cat /proc/modules", 0, "m1 0 0 - Live\n"),
        make_artifact("ls /sys/module/m1/parameters", 1, ""),
    ]
    linux_collector._run_sut_cmd = lambda cmd, seq=seq: seq.pop(0)

    result, data = linux_collector.collect_data()

    assert result.status == ExecutionStatus.OK
    assert isinstance(data, KernelModuleDataModel)
    evt = result.events[-1]
    assert evt.category == "KERNEL_READ"
    assert evt.priority == EventPriority.INFO.value
    assert result.message == "Kernel modules collected"
    assert data.kernel_modules == {"m1": {"parameters": {}}}


def test_collect_data_linux_error(linux_collector):
    def bad(cmd):
        return make_artifact(cmd, 1, "")

    linux_collector._run_sut_cmd = bad

    result, data = linux_collector.collect_data()
    assert result.status == ExecutionStatus.EXECUTION_FAILURE
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
    assert result.message == "Kernel modules collected"


def test_collect_data_windows_not_found(win_collector):
    win_collector._run_sut_cmd = lambda cmd: make_artifact("wmic os get", 0, "")
    result, data = win_collector.collect_data()
    assert result.status == ExecutionStatus.ERROR
    assert data is None
    evt = result.events[0]
    assert evt.category == EventCategory.OS.value
    assert "Error checking kernel modules" in evt.description
