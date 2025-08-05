from types import SimpleNamespace

import pytest

from nodescraper.enums import EventCategory, EventPriority, ExecutionStatus, OSFamily
from nodescraper.plugins.inband.sysctl.sysctl_collector import SysctlCollector
from nodescraper.plugins.inband.sysctl.sysctldata import SysctlDataModel


@pytest.fixture
def linux_sysctl_collector(system_info, conn_mock):
    system_info.os_family = OSFamily.LINUX
    return SysctlCollector(system_info, conn_mock)


def make_artifact(cmd, exit_code, stdout):
    return SimpleNamespace(command=cmd, exit_code=exit_code, stdout=stdout, stderr="")


def test_collect_data_all_fields_success(linux_sysctl_collector):
    sysctl_fields = SysctlDataModel.model_fields.keys()
    responses = [
        make_artifact(f"sysctl -n {f.replace('_', '.', 1)}", 0, "111") for f in sysctl_fields
    ]

    linux_sysctl_collector._run_sut_cmd = lambda cmd, seq=responses: seq.pop(0)

    result, data = linux_sysctl_collector.collect_data()

    assert result.status == ExecutionStatus.OK
    assert isinstance(data, SysctlDataModel)
    for field in SysctlDataModel.model_fields:
        assert getattr(data, field) == 111

    event = result.events[-1]
    assert event.category == "SYSCTL_READ"
    assert event.priority == EventPriority.INFO.value
    assert result.message == "SYSCTL data collected"


def test_collect_data_all_fail(linux_sysctl_collector):
    def always_fail(cmd):
        return make_artifact(cmd, 1, "")

    linux_sysctl_collector._run_sut_cmd = always_fail
    result, data = linux_sysctl_collector.collect_data()

    assert result.status == ExecutionStatus.ERROR
    assert data is None

    evt = result.events[0]
    assert evt.category == EventCategory.OS.value
    assert "Sysctl settings not read" in result.message
