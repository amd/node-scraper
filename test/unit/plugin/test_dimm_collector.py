from unittest.mock import MagicMock

import pytest

from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.models.systeminfo import OSFamily
from nodescraper.plugins.inband.dimm.dimm_collector import DimmCollector
from nodescraper.plugins.inband.dimm.dimmdata import DimmDataModel


@pytest.fixture
def dimm_collector(system_info, conn_mock):
    return DimmCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


def test_parse_dmi_sizes_totals_and_topology(dimm_collector):
    """'Size: <n> <unit>' lines (dmidecode/smbiosDump) sum to a total + per-size counts."""
    stdout = "        Size: 128 GB\n        Size: 128 GB\n        Size: 64 GB\n"
    assert dimm_collector._parse_dmi_sizes(stdout) == "320GB @ 2 x 128GB 1 x 64GB"


def test_parse_dmi_sizes_empty(dimm_collector):
    """No parseable Size lines yields the zero summary."""
    assert dimm_collector._parse_dmi_sizes("No Module Installed\n") == "0 GB"


def test_collect_esxi(system_info, dimm_collector):
    """ESXi parses DIMM sizes from smbiosDump (same 'Size:' field as dmidecode)."""
    system_info.os_family = OSFamily.ESXI
    dimm_collector._run_sut_cmd = MagicMock(
        return_value=MagicMock(
            exit_code=0,
            stdout="        Size: 128 GB\n        Size: 128 GB\n",
            stderr="",
            command=DimmCollector.CMD_ESXI,
        )
    )

    result, data = dimm_collector.collect_data()
    assert result.status == ExecutionStatus.OK
    assert data == DimmDataModel(dimms="256GB @ 2 x 128GB")


def test_collect_esxi_error(system_info, dimm_collector):
    """A failed esxcli/smbiosDump run yields no DIMM data."""
    system_info.os_family = OSFamily.ESXI
    dimm_collector._run_sut_cmd = MagicMock(
        return_value=MagicMock(
            exit_code=1, stdout="", stderr="boom", command=DimmCollector.CMD_ESXI
        )
    )

    _, data = dimm_collector.collect_data()
    assert data is None
