from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from nodescraper.enums import ExecutionStatus, OSFamily
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.plugins.inband.amdsmi.amdsmi_flavor_collector import (
    AmdSmiFlavorCollector,
)
from nodescraper.plugins.inband.amdsmi.amdsmidata_host import HostDriverAmdSmiVersion


class _Tiny(BaseModel):
    gpu: int


@pytest.fixture
def collector(system_info, conn_mock):
    return AmdSmiFlavorCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


def _cmd(exit_code=0, stdout="", stderr=""):
    return MagicMock(exit_code=exit_code, stdout=stdout, stderr=stderr, command="x")


# ---- driver-flavor detection --------------------------------------------------


def test_loaded_driver_host_linux(collector):
    """gim in lsmod -> host driver flavor."""
    collector.system_info.os_family = OSFamily.LINUX
    collector._run_sut_cmd = MagicMock(return_value=_cmd(stdout="gim 12345 0\namdxcp 1 0"))
    assert collector._get_loaded_gpu_driver() == "gim"
    assert collector.is_host_driver is True
    assert collector.is_guest_driver is False


def test_loaded_driver_guest_linux(collector):
    """amdgpu + hypervisor flag -> guest-VF flavor."""
    collector.system_info.os_family = OSFamily.LINUX
    collector._run_sut_cmd = MagicMock(side_effect=[_cmd(stdout="amdgpu 999 0"), _cmd(stdout="1")])
    assert collector.is_host_driver is False
    assert collector.is_guest_driver is True


def test_loaded_driver_baremetal_linux(collector):
    """amdgpu with no hypervisor flag -> bare-metal (neither host nor guest)."""
    collector.system_info.os_family = OSFamily.LINUX
    collector._run_sut_cmd = MagicMock(side_effect=[_cmd(stdout="amdgpu 999 0"), _cmd(stdout="0")])
    assert collector.is_host_driver is False
    assert collector.is_guest_driver is False


def test_loaded_driver_esxi_host(collector):
    """ESXi reads modules via vmkload_mod; amdgpuv -> host flavor, never virtualized."""
    collector.system_info.os_family = OSFamily.ESXI
    collector._run_sut_cmd = MagicMock(return_value=_cmd(stdout="vmklinux\namdgpuv\nvmkapi"))
    assert collector._get_loaded_gpu_driver() == "amdgpuv"
    assert collector.is_host_driver is True
    assert collector._is_virtualized() is False


def test_loaded_driver_none_means_not_loaded(collector):
    """No known AMD GPU module -> None -> driver not loaded."""
    collector.system_info.os_family = OSFamily.LINUX
    collector._run_sut_cmd = MagicMock(return_value=_cmd(stdout="ext4\nnvme"))
    assert collector._get_loaded_gpu_driver() is None
    assert collector._check_gpu_driver_loaded() is False


def test_loaded_driver_cached(collector):
    """The driver lookup is cached after the first probe."""
    collector.system_info.os_family = OSFamily.LINUX
    run = MagicMock(return_value=_cmd(stdout="gim 1 0"))
    collector._run_sut_cmd = run
    collector._get_loaded_gpu_driver()
    collector._get_loaded_gpu_driver()
    assert run.call_count == 1


# ---- _build_flavor_model ------------------------------------------------------


def test_build_flavor_model_dict(collector):
    out = collector._build_flavor_model(_Tiny, {"gpu": 3})
    assert isinstance(out, _Tiny) and out.gpu == 3


def test_build_flavor_model_none_logs_error(collector):
    assert collector._build_flavor_model(_Tiny, None) is None
    assert any(e.priority.name == "ERROR" for e in collector.result.events)


def test_build_flavor_model_keep_key_drops_missing(collector):
    """Rows without keep_key are dropped silently (non-GPU enumeration rows)."""
    out = collector._build_flavor_model(
        _Tiny, [{"gpu": 0}, {"other": 1}, {"gpu": 2}], keep_key="gpu"
    )
    assert [m.gpu for m in out] == [0, 2]


def test_build_flavor_model_skips_unparseable_row(collector):
    """A present-but-invalid row is skipped and a warning is logged; valid rows kept."""
    out = collector._build_flavor_model(_Tiny, [{"gpu": 0}, {"gpu": "NA"}])
    assert [m.gpu for m in out] == [0]
    assert any(e.priority.name == "WARNING" for e in collector.result.events)


def test_build_flavor_model_return_first(collector):
    out = collector._build_flavor_model(_Tiny, [{"gpu": 7}, {"gpu": 8}], return_first=True)
    assert isinstance(out, _Tiny) and out.gpu == 7


# ---- flavor-aware command dispatch -------------------------------------------


def test_detect_commands_host_uses_help_flag(collector):
    collector._loaded_gpu_driver_cache = "gim"  # force host
    collector._run_amd_smi = MagicMock(return_value="    static  Foo\n    metric  Bar\n")
    cmds = collector.detect_amdsmi_commands()
    collector._run_amd_smi.assert_called_once_with("help")
    assert {"static", "metric"} <= cmds


def test_detect_commands_guest_uses_dash_h(collector):
    collector._loaded_gpu_driver_cache = "amdgpu"  # not host
    collector._run_amd_smi = MagicMock(return_value="    list  Foo\n")
    collector.detect_amdsmi_commands()
    collector._run_amd_smi.assert_called_once_with("-h")


def test_get_static_host_vs_nonhost_subcommand(collector):
    collector.amd_smi_commands = {"static"}
    collector._run_amd_smi_dict = MagicMock(return_value=[{"gpu": 0}, {"no_gpu": 1}])
    collector._loaded_gpu_driver_cache = "gim"  # host
    assert collector.get_static() == [{"gpu": 0}]
    assert collector._run_amd_smi_dict.call_args.args[0] == "static"

    collector._run_amd_smi_dict.reset_mock()
    collector._loaded_gpu_driver_cache = "amdgpu"  # non-host
    collector.get_static()
    assert collector._run_amd_smi_dict.call_args.args[0] == "static -g all"


def test_get_static_unsupported_returns_none(collector):
    collector.amd_smi_commands = set()
    assert collector.get_static() is None


def test_get_metric_unwraps_gpu_data(collector):
    collector.amd_smi_commands = {"metric"}
    collector._loaded_gpu_driver_cache = "gim"
    collector._run_amd_smi_dict = MagicMock(return_value={"gpu_data": [{"gpu": 0}, {"x": 1}]})
    assert collector.get_metric() == [{"gpu": 0}]


def test_get_partition_host_parses_text_table(collector):
    collector.amd_smi_commands = {"partition"}
    collector._loaded_gpu_driver_cache = "gim"  # host: no --json, parse text
    table = "GPU memory accelerator_type accelerator_profile_index partition_id\n0 NPS1 SPX 0 0\n"
    collector._run_amd_smi = MagicMock(return_value=table)
    out = collector.get_partition()
    assert out == {
        "current_partition": [
            {
                "gpu_id": 0,
                "memory": "NPS1",
                "accelerator_type": "SPX",
                "accelerator_profile_index": "0",
                "partition_id": "0",
            }
        ]
    }


def test_get_xgmi_flags_host_vs_guest(collector):
    collector.amd_smi_commands = {"xgmi"}
    collector._loaded_gpu_driver_cache = "gim"  # host
    collector._run_amd_smi_dict = MagicMock(return_value=[])
    collector.get_xgmi_data_metric()
    flags = [c.args[0] for c in collector._run_amd_smi_dict.call_args_list]
    assert "xgmi --metric" in flags and "xgmi --link-status" in flags

    collector._run_amd_smi_dict.reset_mock()
    collector._loaded_gpu_driver_cache = "amdgpu"  # guest/bare-metal
    collector.get_xgmi_data_metric()
    flags = [c.args[0] for c in collector._run_amd_smi_dict.call_args_list]
    assert "xgmi -m" in flags and "xgmi -l" in flags


def test_version_model_selected_by_flavor(collector):
    collector._loaded_gpu_driver_cache = "gim"  # host
    collector._run_amd_smi_dict = MagicMock(
        return_value={"version": "1.0", "amdsmi_library_version": "37.0.5"}
    )
    out = collector._get_amdsmi_version()
    assert isinstance(out, HostDriverAmdSmiVersion)


# ---- collect_data guard -------------------------------------------------------


def test_collect_data_no_driver_not_ran(collector):
    collector._check_amdsmi_installed = MagicMock(return_value=True)
    collector._run_sut_cmd = MagicMock(return_value=_cmd(stdout="ext4"))  # no driver
    result, data = collector.collect_data()
    assert result.status == ExecutionStatus.NOT_RAN
    assert data is None
