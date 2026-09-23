###############################################################################
#
# MIT License
#
# Copyright (c) 2026 Advanced Micro Devices, Inc.
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
from unittest.mock import MagicMock

import pytest

from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.plugins.inband.pcie.collector_args import PcieCollectorArgs
from nodescraper.plugins.inband.pcie.pcie_collector import PcieCollector


@pytest.fixture
def collector(system_info, conn_mock):
    return PcieCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


LSPCI_PP_D_MULTI_DOMAIN_OUTPUT = (
    "0001:00:01.1/00:02.0/00:03.0 Processing accelerators: Advanced Micro Devices, Inc."
)

LSPCI_PP_D_SINGLE_DOMAIN_OUTPUT = (
    "00:01.1/00:02.0/00:03.0 Processing accelerators: Advanced Micro Devices, Inc."
)


def test_get_upstream_bdf_uses_lspci_pp_d_command(collector):
    """Upstream BDF lookup must use lspci -PP -D -d for multi-domain path output."""
    collector._run_os_cmd = MagicMock(return_value=LSPCI_PP_D_MULTI_DOMAIN_OUTPUT)

    collector._get_upstream_bdf_from_buspath("1002", "74a1")

    collector._run_os_cmd.assert_called_once_with(
        collector.CMD_LSPCI_PATH_DEVICE_DOMAIN.format(vendor_id="1002", dev_id="74a1"),
        sudo=True,
    )


def test_get_upstream_bdf_propagates_domain_prefix(collector):
    """Bare downstream BDFs inherit the domain prefix from the root path component."""
    collector._run_os_cmd = MagicMock(return_value=LSPCI_PP_D_MULTI_DOMAIN_OUTPUT)

    upstream_bdfs = collector._get_upstream_bdf_from_buspath("1002", "74a1", upstream_steps_limit=2)

    assert upstream_bdfs == {
        "0001:00:03.0": ["0001:00:03.0", "0001:00:02.0", "0001:00:01.1"],
    }


def test_get_upstream_bdf_defaults_domain_to_0000(collector):
    """When no domain prefix is present, bare BDFs default to domain 0000."""
    collector._run_os_cmd = MagicMock(return_value=LSPCI_PP_D_SINGLE_DOMAIN_OUTPUT)

    upstream_bdfs = collector._get_upstream_bdf_from_buspath("1002", "74a1", upstream_steps_limit=1)

    assert upstream_bdfs == {
        "0000:00:03.0": ["0000:00:03.0", "0000:00:02.0"],
    }


def test_show_lspci_path_domain_uses_correct_command(collector):
    """Artifact collection runs lspci -PP -D."""
    collector._run_os_cmd = MagicMock(return_value="0001:00:01.1/00:02.0")

    result = collector.show_lspci_path_domain(sudo=False)

    collector._run_os_cmd.assert_called_once_with(collector.CMD_LSPCI_PATH_DOMAIN, sudo=False)
    assert result == "0001:00:01.1/00:02.0"


def test_log_pcie_artifacts_includes_lspci_pp_d(collector):
    """Domain-prefixed path view is saved as lspci_pp_d.txt."""
    collector._log_pcie_artifacts(
        lspci_pp="00:03.0/00:02.0",
        lspci_pp_d="0001:00:01.1/0001:00:02.0/0001:00:03.0",
        lspci_hex="00:",
        lspci_verbose_tree="tree",
        lspci_verbose="verbose",
    )

    artifact_names = {artifact.filename for artifact in collector.result.artifacts}
    assert "lspci_pp_d.txt" in artifact_names
    lspci_pp_d = next(
        artifact for artifact in collector.result.artifacts if artifact.filename == "lspci_pp_d.txt"
    )
    assert lspci_pp_d.contents == "0001:00:01.1/0001:00:02.0/0001:00:03.0"


# Mixed-vendor `lspci -D -nn` output: AMD GPU (1002), Intel NIC (8086),
# Samsung NVMe (144d), ASPEED BMC/VGA (1a03).
LSPCI_D_NN_MIXED_VENDOR_OUTPUT = "\n".join(
    [
        "0000:01:00.0 Processing accelerators [1200]: Advanced Micro Devices, Inc. [1002:74a1]",
        "0000:02:00.0 Ethernet controller [0200]: Intel Corporation [8086:1572]",
        "0000:03:00.0 Non-Volatile memory controller [0108]: Samsung Electronics [144d:a80a]",
        "0000:04:00.0 VGA compatible controller [0300]: ASPEED Technology, Inc. [1a03:2000]",
    ]
)


def _mock_run_sut_cmd_result(stdout: str, exit_code: int = 0, stderr: str = ""):
    result = MagicMock()
    result.exit_code = exit_code
    result.stdout = stdout
    result.stderr = stderr
    return result


def _fake_run(outputs: dict):
    """Return a _run_sut_cmd side effect that answers by command; others get empty output."""

    def run(cmd, *args, **kwargs):
        return _mock_run_sut_cmd_result(outputs.get(cmd, ""))

    return run


def test_detect_other_devices_excludes_amd_and_returns_non_amd_bdfs(collector):
    """_detect_other_devices returns non-AMD BDFs and excludes AMD (vendorid_ep) devices."""
    collector._run_sut_cmd = MagicMock(
        side_effect=_fake_run({collector.CMD_LSPCI_ALL_DEVICES: LSPCI_D_NN_MIXED_VENDOR_OUTPUT})
    )

    other_bdfs = collector._detect_other_devices()

    # AMD BDF (0000:01:00.0) must be excluded; the three non-AMD BDFs included.
    assert other_bdfs == [
        "0000:02:00.0",
        "0000:03:00.0",
        "0000:04:00.0",
    ]
    collector._run_sut_cmd.assert_any_call(
        collector.CMD_LSPCI_ALL_DEVICES,
        sudo=False,
        log_artifact=False,
    )


def test_detect_other_devices_empty_when_only_amd(collector):
    """When all devices are AMD, _detect_other_devices returns an empty list."""
    amd_only = "0000:01:00.0 Processing accelerators [1200]: AMD [1002:74a1]"
    collector._run_sut_cmd = MagicMock(return_value=_mock_run_sut_cmd_result(amd_only))

    assert collector._detect_other_devices() == []


def test_detect_other_devices_handles_command_failure(collector):
    """A failed lspci command yields None (not collected) and logs an error."""
    collector._run_sut_cmd = MagicMock(
        return_value=_mock_run_sut_cmd_result("", exit_code=1, stderr="boom")
    )

    assert collector._detect_other_devices() is None
    assert "Failed to enumerate PCI devices" in [e.description for e in collector.result.events]


def test_collect_all_devices_false_leaves_other_cfg_space_none(collector):
    """By default, other_pcie_cfg_space stays None and all-device enumeration isn't run."""

    def fake_run(cmd, *args, **kwargs):
        return _mock_run_sut_cmd_result("")

    spy = MagicMock(side_effect=fake_run)
    collector._run_sut_cmd = spy

    _, pcie_data = collector.collect_data(PcieCollectorArgs(collect_all_devices=False))

    assert pcie_data is not None
    assert pcie_data.other_pcie_cfg_space is None
    # The all-devices enumeration command must NOT be issued in the default path.
    issued = [call.args[0] for call in spy.call_args_list]
    assert collector.CMD_LSPCI_ALL_DEVICES not in issued


def _hex_rows(vendor_id: int, device_id: int, base_class: int) -> str:
    """Build the 64-byte lspci -x hex rows for a device with no capabilities."""
    config = [0] * 64
    config[0x00], config[0x01] = vendor_id & 0xFF, vendor_id >> 8
    config[0x02], config[0x03] = device_id & 0xFF, device_id >> 8
    config[0x0B] = base_class
    # Point the capability list past the 64 bytes so no capabilities are parsed.
    config[0x34] = 0x40
    return "\n".join(
        f"{offset:02x}:" + "".join(f" {byte:02x}" for byte in config[offset : offset + 16])
        for offset in range(0, 64, 16)
    )


# Full `lspci -x` dump. lspci omits the domain on single-domain systems.
LSPCI_X_FULL_DUMP = "\n\n".join(
    [
        "02:00.0 Ethernet controller: Intel Corporation Device 1572\n"
        + _hex_rows(0x8086, 0x1572, 0x02),
        "03:00.0 Non-Volatile memory controller: Samsung Electronics Device a80a\n"
        + _hex_rows(0x144D, 0xA80A, 0x01),
        "04:00.0 VGA compatible controller: ASPEED Technology, Inc. Device 2000\n"
        + _hex_rows(0x1A03, 0x2000, 0x03),
    ]
)

_ALL_OTHER_BDFS = {"0000:02:00.0", "0000:03:00.0", "0000:04:00.0"}


def test_collect_all_devices_true_parses_full_dump(collector):
    """With collect_all_devices=True, non-AMD config space comes from the single
    full lspci dump, with no per-device lspci calls."""
    collector._run_sut_cmd = MagicMock(
        side_effect=_fake_run(
            {
                collector.CMD_LSPCI_ALL_DEVICES: LSPCI_D_NN_MIXED_VENDOR_OUTPUT,
                collector.CMD_LSPCI_HEX: LSPCI_X_FULL_DUMP,
            }
        )
    )

    _, pcie_data = collector.collect_data(PcieCollectorArgs(collect_all_devices=True))

    assert pcie_data is not None
    assert set(pcie_data.other_pcie_cfg_space) == _ALL_OTHER_BDFS
    nic = pcie_data.other_pcie_cfg_space["0000:02:00.0"].type_0_configuration
    assert nic.vendor_id.val == 0x8086
    assert nic.class_code.val == 0x02
    issued = [call.args[0] for call in collector._run_sut_cmd.call_args_list]
    assert not [cmd for cmd in issued if " -s " in cmd]


def test_other_device_missing_from_dump_is_read_individually(collector):
    """A device absent from the full dump falls back to a per-device lspci read."""
    partial_dump = LSPCI_X_FULL_DUMP.split("\n\n04:00.0")[0]
    per_device_cmd = "lspci -x -s 0000:04:00.0"
    collector._run_sut_cmd = MagicMock(
        side_effect=_fake_run(
            {
                collector.CMD_LSPCI_ALL_DEVICES: LSPCI_D_NN_MIXED_VENDOR_OUTPUT,
                collector.CMD_LSPCI_HEX: partial_dump,
                per_device_cmd: "04:00.0 VGA\n" + _hex_rows(0x1A03, 0x2000, 0x03),
            }
        )
    )

    _, pcie_data = collector.collect_data(PcieCollectorArgs(collect_all_devices=True))

    assert set(pcie_data.other_pcie_cfg_space) == _ALL_OTHER_BDFS
    issued = [call.args[0] for call in collector._run_sut_cmd.call_args_list]
    assert per_device_cmd in issued


def test_unreadable_other_device_is_omitted(collector):
    """A device whose config space can't be read is left out, not stored as an
    empty PcieCfgSpace whose None registers would look like errors."""
    partial_dump = LSPCI_X_FULL_DUMP.split("\n\n04:00.0")[0]
    collector._run_sut_cmd = MagicMock(
        side_effect=_fake_run(
            {
                collector.CMD_LSPCI_ALL_DEVICES: LSPCI_D_NN_MIXED_VENDOR_OUTPUT,
                collector.CMD_LSPCI_HEX: partial_dump,
            }
        )
    )

    _, pcie_data = collector.collect_data(PcieCollectorArgs(collect_all_devices=True))

    assert set(pcie_data.other_pcie_cfg_space) == {"0000:02:00.0", "0000:03:00.0"}
    assert "Hex data is not the expected length" in [e.description for e in collector.result.events]


def test_collect_all_devices_enumeration_failure_leaves_none(collector):
    """If lspci enumeration fails, other_pcie_cfg_space is None (not collected),
    so the analyzer does not report 0 NICs."""

    def run(cmd, *args, **kwargs):
        if cmd == collector.CMD_LSPCI_ALL_DEVICES:
            return _mock_run_sut_cmd_result("", exit_code=1, stderr="boom")
        return _mock_run_sut_cmd_result("")

    collector._run_sut_cmd = MagicMock(side_effect=run)

    _, pcie_data = collector.collect_data(PcieCollectorArgs(collect_all_devices=True))

    assert pcie_data.other_pcie_cfg_space is None


def test_detect_other_devices_excludes_vfs(collector):
    """SR-IOV VFs are excluded, whether found via sysfs physfn or by lspci description."""
    lspci_output = "\n".join(
        [
            "0000:02:00.0 Ethernet controller [0200]: Mellanox Technologies [15b3:1021]",
            "0000:02:00.1 Ethernet controller [0200]: Mellanox Technologies [15b3:1021]",
            "0000:02:00.2 Ethernet controller [0200]: Mellanox Technologies [15b3:101e]",
            "0000:05:02.0 Ethernet controller [0200]: Intel Corporation Ethernet "
            "Adaptive Virtual Function [8086:1889]",
        ]
    )
    collector._run_sut_cmd = MagicMock(
        side_effect=_fake_run(
            {
                collector.CMD_LSPCI_ALL_DEVICES: lspci_output,
                collector.CMD_LIST_VFS: "/sys/bus/pci/devices/0000:02:00.2/physfn",
            }
        )
    )

    assert collector._detect_other_devices() == ["0000:02:00.0", "0000:02:00.1"]


def test_get_other_cfg_space_skips_already_collected(collector):
    """BDFs already collected on the AMD path (e.g. upstream switches) are skipped."""
    cfg_spaces = collector._get_other_cfg_space(
        sorted(_ALL_OTHER_BDFS),
        already_collected={"0000:02:00.0"},
        lspci_hex=LSPCI_X_FULL_DUMP,
        sudo=False,
    )

    assert set(cfg_spaces) == {"0000:03:00.0", "0000:04:00.0"}


def test_split_lspci_hex_dump_handles_domain_and_bare_bdfs(collector):
    """Bare BDFs get the 0000 domain; domain-qualified BDFs are kept."""
    dump = "\n\n".join(
        [
            "02:00.0 Ethernet controller: Intel\n" + _hex_rows(0x8086, 0x1572, 0x02),
            "0001:03:00.0 Ethernet controller: Intel\n" + _hex_rows(0x8086, 0x1572, 0x02),
        ]
    )

    blocks = collector._split_lspci_hex_dump(dump)

    assert set(blocks) == {"0000:02:00.0", "0001:03:00.0"}
    assert len(collector.parse_hex_dump(blocks["0001:03:00.0"])) == 64


def test_collect_data_uses_args_model(collector):
    """Collector args drive collection, including an explicit full upstream path (None)."""
    collector._get_pcie_data = MagicMock(return_value=None)

    collector.collect_data(
        PcieCollectorArgs(upstream_steps_to_collect=None, collect_all_devices=True)
    )

    collector._get_pcie_data.assert_called_once_with(None, collect_all_devices=True)


def test_collect_data_accepts_dict_args(collector):
    """A config-file dict is validated into PcieCollectorArgs by the collect decorator."""
    collector._get_pcie_data = MagicMock(return_value=None)

    collector.collect_data({"upstream_steps_to_collect": 2, "collect_all_devices": True})

    collector._get_pcie_data.assert_called_once_with(2, collect_all_devices=True)


def test_collect_data_defaults_to_amd_only(collector):
    """With no args, only AMD devices are collected along their full upstream path."""
    collector._get_pcie_data = MagicMock(return_value=None)

    collector.collect_data()

    collector._get_pcie_data.assert_called_once_with(None, collect_all_devices=False)
