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
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from nodescraper.enums.eventcategory import EventCategory
from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.models.systeminfo import OSFamily
from nodescraper.plugins.inband.dimm.collector_args import DimmCollectorArgs
from nodescraper.plugins.inband.dimm.dimm_collector import DimmCollector
from nodescraper.plugins.inband.dimm.dimmdata import DimmDataModel

FIXTURES = Path(__file__).parent / "fixtures"

# `dmidecode -q --type 17` from a dual socket host, 24 slots of Samsung DDR5.
# Being quiet, it carries no handle lines naming the DMI type, so a record is
# only identifiable by its section title and closed by a blank line.
QUIET_DUMP = (FIXTURES / "dmidecode_quiet.txt").read_text()

# An unfiltered dump, where every record opens with a handle line naming its
# type. It covers the awkward records a real fleet throws up: a type 16 array
# whose size is not a module at all, a module sized in megabytes that nests a
# further volatile size, an empty slot, and placeholder manufacturer text.
FULL_DUMP = (FIXTURES / "dmidecode_full.txt").read_text()

# `wmic memorychip get /format:csv` output from a host with soldered LPDDR5.
WMIC_DUMP = (FIXTURES / "dmideode_wmic.txt").read_text()


@pytest.fixture
def collector(system_info, conn_mock):
    system_info.os_family = OSFamily.LINUX
    return DimmCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


@pytest.fixture
def windows_collector(system_info, conn_mock):
    system_info.os_family = OSFamily.WINDOWS
    return DimmCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


def cmd_result(exit_code=0, stdout="", stderr="", command="dmidecode"):
    """Build a stand in for the CommandArtifact that _run_sut_cmd returns."""
    return MagicMock(exit_code=exit_code, stdout=stdout, stderr=stderr, command=command)


def descriptions(result):
    """List the description of every event logged against a result."""
    return [event.description for event in result.events]


def linux_run(collector, targeted=QUIET_DUMP, full=FULL_DUMP):
    """Collect with the full dump and the targeted dump each stubbed out."""
    collector._run_sut_cmd = MagicMock(
        side_effect=[cmd_result(stdout=full), cmd_result(stdout=targeted)]
    )
    return collector.collect_data()


def test_run_linux(collector):
    result, data = linux_run(collector)

    assert result.status == ExecutionStatus.OK
    assert data.dimm_count == 24
    assert data.total_size_bytes == 24 * 96 * 1024**3
    assert data.total_size == "2304GB"
    assert data.population == {"96GB": 24}
    assert str(data) == "2304GB @ 24 x 96GB"
    assert result.message == "DIMM: 2304GB @ 24 x 96GB"


def test_run_linux_decodes_every_field(collector):
    _, data = linux_run(collector)
    dimm = data.dimms[0]

    assert dimm.size_bytes == 96 * 1024**3
    assert dimm.size == "96GB"
    assert dimm.locator == "CPU0_A"
    assert dimm.bank_locator == "_Node0_Channel0_Dimm0"
    assert dimm.manufacturer == "Samsung"
    # dmidecode pads the part number out to its full field width.
    assert dimm.part_number == "M321RYGA0PB0-CWMXJ"
    assert dimm.serial_number == "2432-50F82DCB"
    assert dimm.memory_type == "DDR5"
    assert dimm.form_factor == "DIMM"
    assert dimm.speed_mts == 5600
    assert dimm.configured_speed_mts == 5600
    assert dimm.rank == 2
    assert dimm.data_width_bits == 64
    assert dimm.total_width_bits == 80
    assert str(dimm) == "CPU0_A: 96GB DDR5 5600MT/s Samsung"


def test_run_linux_covers_every_slot(collector):
    _, data = linux_run(collector)

    assert [dimm.locator for dimm in data.dimms] == [
        f"CPU{cpu}_{channel}" for cpu in (0, 1) for channel in "ABCDEFGHIJKL"
    ]


def test_run_linux_keeps_full_dump_as_artifact(collector):
    result, _ = linux_run(collector)

    artifacts = [a for a in result.artifacts if a.filename == "dmidecode.txt"]
    assert len(artifacts) == 1
    assert artifacts[0].contents == FULL_DUMP


def test_run_linux_parses_unfiltered_dump(collector):
    # The targeted dump fails, so the records come from the full dump instead.
    collector._run_sut_cmd = MagicMock(
        side_effect=[
            cmd_result(stdout=FULL_DUMP),
            cmd_result(exit_code=1, stderr="invalid option -- 'q'"),
        ]
    )

    _, data = collector.collect_data()

    # The type 16 array size, the nested volatile size and the empty slot are
    # all left out, and the megabyte size normalises against the gigabyte one.
    assert data.dimm_count == 2
    assert [dimm.locator for dimm in data.dimms] == ["DIMM_A1", "DIMM_B1"]
    assert str(data) == "80GB @ 1 x 16GB 1 x 64GB"


def test_run_linux_drops_placeholder_text(collector):
    collector._run_sut_cmd = MagicMock(
        side_effect=[
            cmd_result(stdout=FULL_DUMP),
            cmd_result(exit_code=1, stderr="invalid option -- 'q'"),
        ]
    )

    _, data = collector.collect_data()
    dimm = data.dimms[1]

    assert dimm.manufacturer is None
    # A serial of all zeroes is a real value rather than a placeholder.
    assert dimm.serial_number == "00000000"
    assert str(dimm) == "DIMM_B1: 64GB DDR5 4800MT/s"


def test_run_linux_warns_when_full_dump_fails(collector):
    collector._run_sut_cmd = MagicMock(
        side_effect=[
            cmd_result(exit_code=1, stderr="command not found"),
            cmd_result(stdout=QUIET_DUMP),
        ]
    )

    result, data = collector.collect_data()

    # The inventory still comes back, the missing artifact is only a warning.
    assert data.dimm_count == 24
    assert "Could not collect full dmidecode output" in descriptions(result)
    assert not [a for a in result.artifacts if a.filename == "dmidecode.txt"]


def test_run_linux_retries_without_sudo(collector):
    collector._run_sut_cmd = MagicMock(
        side_effect=[
            cmd_result(exit_code=127, stderr="sudo: command not found"),
            cmd_result(stdout=FULL_DUMP),
            cmd_result(exit_code=127, stderr="sudo: command not found"),
            cmd_result(stdout=QUIET_DUMP),
        ]
    )

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.OK
    assert data.dimm_count == 24
    assert [call.kwargs["sudo"] for call in collector._run_sut_cmd.call_args_list] == [
        True,
        False,
        True,
        False,
    ]


def test_run_linux_error(collector):
    collector._run_sut_cmd = MagicMock(
        return_value=cmd_result(exit_code=1, stderr="Error occurred")
    )

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.ERROR
    assert data is None
    assert result.message.startswith("DIMM info not found")
    assert descriptions(result) == [
        "Error checking dimms",
        "Could not collect full dmidecode output",
        "Error checking dimms",
        "DIMM info not found",
    ]
    assert result.events[0].category == EventCategory.OS.value


def test_run_linux_no_modules_installed(collector):
    empty = "Memory Device\n\tSize: No Module Installed\n\tLocator: DIMM_A1\n"

    result, data = linux_run(collector, targeted=empty)

    assert result.status == ExecutionStatus.ERROR
    assert data is None
    assert "DIMM info not found" in descriptions(result)


def test_skip_sudo(collector):
    collector._run_sut_cmd = MagicMock()

    result, data = collector.collect_data(DimmCollectorArgs(skip_sudo=True))

    assert result.status == ExecutionStatus.NOT_RAN
    assert data is None
    collector._run_sut_cmd.assert_not_called()


def test_run_windows(windows_collector):
    windows_collector._run_sut_cmd = MagicMock(return_value=cmd_result(stdout=WMIC_DUMP))

    result, data = windows_collector.collect_data()

    assert result.status == ExecutionStatus.OK
    assert data.dimm_count == 4
    assert data.total_size_bytes == 4 * 8 * 1024**3
    assert data.population == {"8GB": 4}
    assert str(data) == "32GB @ 4 x 8GB"
    windows_collector._run_sut_cmd.assert_called_once_with(DimmCollector.CMD_WINDOWS)


def test_run_windows_decodes_every_field(windows_collector):
    windows_collector._run_sut_cmd = MagicMock(return_value=cmd_result(stdout=WMIC_DUMP))

    _, data = windows_collector.collect_data()
    dimm = data.dimms[0]

    # Capacity arrives as a bare byte count rather than a "8 GB" style size.
    assert dimm.size_bytes == 8 * 1024**3
    assert dimm.size == "8GB"
    assert dimm.locator == "DIMM 0"
    assert dimm.bank_locator == "P0 CHANNEL A"
    assert dimm.manufacturer == "Micron Technology"
    assert dimm.part_number == "MT62F2G32D8DR-031 WT"
    assert dimm.serial_number == "00000000"
    # SMBIOSMemoryType 35 and FormFactor 1 are raw enum codes on Windows, and
    # the two enumerations do not share a numbering.
    assert dimm.memory_type == "LPDDR5"
    assert dimm.form_factor == "Other"
    assert dimm.speed_mts == 6400
    assert dimm.configured_speed_mts == 6400
    assert dimm.rank is None
    assert dimm.data_width_bits == 32
    assert dimm.total_width_bits == 32
    assert str(dimm) == "DIMM 0: 8GB LPDDR5 6400MT/s Micron Technology"


def test_run_windows_covers_every_slot(windows_collector):
    windows_collector._run_sut_cmd = MagicMock(return_value=cmd_result(stdout=WMIC_DUMP))

    result, data = windows_collector.collect_data()

    # Every module reports the same device locator, so only the bank tells the
    # four soldered channels apart.
    assert [dimm.bank_locator for dimm in data.dimms] == [
        "P0 CHANNEL A",
        "P0 CHANNEL B",
        "P0 CHANNEL C",
        "P0 CHANNEL D",
    ]
    assert len([a for a in result.artifacts if a.filename == "memorychip.csv"]) == 1


def test_run_windows_error(windows_collector):
    windows_collector._run_sut_cmd = MagicMock(
        return_value=cmd_result(exit_code=1, stderr="Invalid query", command="wmic")
    )

    result, data = windows_collector.collect_data()

    assert result.status == ExecutionStatus.ERROR
    assert data is None
    assert descriptions(result) == ["Error checking dimms", "DIMM info not found"]


def test_empty_model():
    data = DimmDataModel()

    assert data.dimm_count == 0
    assert data.total_size_bytes == 0
    assert data.population == {}
    assert str(data) == "0GB"
