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
