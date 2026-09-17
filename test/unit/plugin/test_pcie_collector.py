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

from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.plugins.inband.pcie.collector_args import PcieCollectorArgs
from nodescraper.plugins.inband.pcie.pcie_collector import PcieCollector
from nodescraper.plugins.inband.pcie.pcie_data import PcieCfgSpace


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


# --- ESXi -------------------------------------------------------------------

# esxcli hardware pci list: bare BDF header lines, then indented fields.
ESXCLI_PCI_LIST = (
    "0000:05:00.0\n"
    "   Device ID: 0x75a3\n"  # PF
    "0000:15:00.0\n"
    "   Device ID: 0x0000744C\n"  # padded + uppercase -> 0x744c
    "0000:05:02.0\n"
    "   Device ID: 0x75b3\n"  # VF
    "0000:99:00.0\n"
    "   SubDevice ID: 0x75a3\n"  # must NOT be treated as a Device ID
    "   Device ID: 0xdead\n"  # no match
)

# lspci -e: "<bdf> <description>" header lines, then hex rows.
LSPCI_E_BLOB = (
    "0000:05:00.0 Processing accelerators: AMD\n"
    "00: 12 34 56 78\n"
    "10: 9a bc de f0\n"
    "0000:05:02.0 Processing accelerators: AMD VF\n"
    "00: aa bb cc dd\n"
)


def test_get_gpu_vf_bdfs_esxi_matches_pf_and_vf(collector):
    """PF/VF BDFs are selected by matching the expected device IDs."""
    collector._run_os_cmd = MagicMock(return_value=ESXCLI_PCI_LIST)
    pf, vf = collector._get_gpu_vf_bdfs_esxi(0x75A3, 0x75B3)
    assert pf == ["0000:05:00.0"]
    assert vf == ["0000:05:02.0"]


def test_get_gpu_vf_bdfs_esxi_case_and_padding(collector):
    """A padded/uppercase Device ID ("0x0000744C") matches the expected 0x744c."""
    collector._run_os_cmd = MagicMock(return_value=ESXCLI_PCI_LIST)
    pf, vf = collector._get_gpu_vf_bdfs_esxi(0x744C, None)
    assert pf == ["0000:15:00.0"]
    assert vf == []


def test_get_gpu_vf_bdfs_esxi_both_none_short_circuits(collector):
    """With no expected device IDs, esxcli is not even queried."""
    collector._run_os_cmd = MagicMock(return_value=ESXCLI_PCI_LIST)
    pf, vf = collector._get_gpu_vf_bdfs_esxi(None, None)
    assert (pf, vf) == ([], [])
    collector._run_os_cmd.assert_not_called()


def test_get_gpu_vf_bdfs_esxi_ignores_unparseable_id(collector):
    """A non-hex Device ID value is skipped rather than raising."""
    collector._run_os_cmd = MagicMock(
        return_value="0000:05:00.0\n   Device ID: N/A\n0000:05:02.0\n   Device ID: 0x75a3\n"
    )
    pf, vf = collector._get_gpu_vf_bdfs_esxi(0x75A3, None)
    assert pf == ["0000:05:02.0"]


def test_get_all_cfg_space_esxi_splits_by_bdf(collector):
    """lspci -e is split into {bdf: hex-rows} and saved as an artifact."""
    collector._run_os_cmd = MagicMock(return_value=LSPCI_E_BLOB)
    cfg = collector._get_all_cfg_space_esxi()
    assert set(cfg) == {"0000:05:00.0", "0000:05:02.0"}
    assert cfg["0000:05:00.0"] == "00: 12 34 56 78\n10: 9a bc de f0"
    assert any(a.filename == "lspci_e.txt" for a in collector.result.artifacts)


def test_get_all_cfg_space_esxi_empty(collector):
    """No lspci output -> empty mapping."""
    collector._run_os_cmd = MagicMock(return_value="")
    assert collector._get_all_cfg_space_esxi() == {}


def test_get_pcie_data_esxi_no_bdfs_warns(collector):
    """When no GPU/VF BDFs match, a warning is logged and None returned."""
    collector._get_gpu_vf_bdfs_esxi = MagicMock(return_value=([], []))
    assert collector._get_pcie_data_esxi(0x75A3, None) is None
    assert any("No GPU/VF BDFs" in e.description for e in collector.result.events)


def test_get_pcie_data_esxi_empty_cfg_errors(collector):
    """BDFs found but no config space dump -> ERROR status, None."""
    collector._get_gpu_vf_bdfs_esxi = MagicMock(return_value=(["0000:05:00.0"], []))
    collector._get_all_cfg_space_esxi = MagicMock(return_value={})
    assert collector._get_pcie_data_esxi(0x75A3, None) is None
    assert collector.result.status == ExecutionStatus.ERROR


def test_get_pcie_data_esxi_builds_model(collector):
    """PF/VF BDFs present in the cfg dump are parsed into the PcieDataModel."""
    collector._get_gpu_vf_bdfs_esxi = MagicMock(return_value=(["0000:05:00.0"], ["0000:05:02.0"]))
    collector._get_all_cfg_space_esxi = MagicMock(
        return_value={"0000:05:00.0": "pf-hex", "0000:05:02.0": "vf-hex"}
    )
    collector._cfg_space_from_hex = MagicMock(return_value=PcieCfgSpace())

    data = collector._get_pcie_data_esxi(0x75A3, 0x75B3)
    assert list(data.pcie_cfg_space) == ["0000:05:00.0"]
    assert list(data.vf_pcie_cfg_space) == ["0000:05:02.0"]
    collector._cfg_space_from_hex.assert_any_call("pf-hex", "0000:05:00.0")
    collector._cfg_space_from_hex.assert_any_call("vf-hex", "0000:05:02.0")


def test_cfg_space_from_hex_too_short_logs_error(collector):
    """Fewer than 64 parsed bytes logs an error (short/truncated dump)."""
    collector._cfg_space_from_hex("00: 12 34 56 78", "0000:05:00.0")
    assert any("not the expected length" in e.description for e in collector.result.events)


def test_collect_data_threads_devid_from_args(collector):
    """collect_data forwards args.devid_ep / devid_ep_vf into the ESXi resolver."""
    collector._get_pcie_data = MagicMock(return_value=None)
    args = PcieCollectorArgs(devid_ep=0x75A3, devid_ep_vf=0x75B3)
    collector.collect_data(args)
    collector._get_pcie_data.assert_called_once_with(None, 0x75A3, 0x75B3)
