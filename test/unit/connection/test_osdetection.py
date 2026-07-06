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
import json

from nodescraper.connection.inband import CommandArtifact
from nodescraper.connection.inband.inbandmanager import InBandConnectionManager
from nodescraper.connection.inband.osdetection import (
    ARISTA_VERSION_CMD,
    DELL_VERSION_CMD,
    detect_network_os,
    parse_arista_version_output,
    parse_dell_sonic_version_output,
)
from nodescraper.enums import OSFamily

DUMMY_ARISTA_VERSION = {
    "mfgName": "Arista Networks",
    "version": "4.32.1F",
    "modelName": "DCS-7280CR3-32P4",
    "serialNumber": "JPE12345678",
    "architecture": "x86_64",
}
DUMMY_ARISTA_VERSION_JSON = json.dumps(DUMMY_ARISTA_VERSION)

DUMMY_ARISTA_VERSION_MINIMAL = {
    "mfgName": "Arista Networks",
    "version": "4.28.0F",
}
DUMMY_ARISTA_VERSION_MINIMAL_JSON = json.dumps(DUMMY_ARISTA_VERSION_MINIMAL)

DUMMY_NON_ARISTA_VERSION_JSON = json.dumps({"mfgName": "Cisco Systems", "version": "1.0"})

DUMMY_DELL_SONIC_VERSION_TEXT = """\
Dell EMC Enterprise SONiC
SONiC Software Version: 4.1.0-Enterprise
HwSKU: DellEMC-S5248F-ON
Serial Number: CN0123456789AB
"""

DUMMY_DELL_SONIC_VERSION_MINIMAL_TEXT = """\
Dell SONiC
SONiC Software Version: 4.0.0
"""

DUMMY_CISCO_NXOS_VERSION_TEXT = "Cisco NX-OS Software"

DUMMY_UNAME_LINUX = CommandArtifact(
    command="uname -s",
    stdout="Linux",
    stderr="",
    exit_code=0,
)

DUMMY_UNAME_FAILED = CommandArtifact(
    command="uname -s",
    stdout="",
    stderr="invalid command",
    exit_code=1,
)

DUMMY_ARISTA_VERSION_CMD_OK = CommandArtifact(
    command=ARISTA_VERSION_CMD,
    stdout=DUMMY_ARISTA_VERSION_JSON,
    stderr="",
    exit_code=0,
)

DUMMY_ARISTA_VERSION_CMD_FAILED = CommandArtifact(
    command=ARISTA_VERSION_CMD,
    stdout="",
    stderr="invalid",
    exit_code=1,
)

DUMMY_DELL_VERSION_CMD_OK = CommandArtifact(
    command=DELL_VERSION_CMD,
    stdout=DUMMY_DELL_SONIC_VERSION_TEXT,
    stderr="",
    exit_code=0,
)

DUMMY_DELL_VERSION_CMD_MINIMAL_OK = CommandArtifact(
    command=DELL_VERSION_CMD,
    stdout=DUMMY_DELL_SONIC_VERSION_MINIMAL_TEXT,
    stderr="",
    exit_code=0,
)

DUMMY_DELL_VERSION_CMD_NON_DELL = CommandArtifact(
    command=DELL_VERSION_CMD,
    stdout=DUMMY_CISCO_NXOS_VERSION_TEXT,
    stderr="",
    exit_code=0,
)


def test_parse_arista_version_output_success():
    detection = parse_arista_version_output(DUMMY_ARISTA_VERSION_JSON)

    assert detection is not None
    assert detection.os_family == OSFamily.EOS
    assert detection.platform == "Arista EOS"
    assert detection.metadata == {
        "os_version": DUMMY_ARISTA_VERSION["version"],
        "device_model": DUMMY_ARISTA_VERSION["modelName"],
    }


def test_parse_arista_version_output_rejects_non_arista():
    assert parse_arista_version_output(DUMMY_NON_ARISTA_VERSION_JSON) is None


def test_parse_dell_sonic_version_output_success():
    detection = parse_dell_sonic_version_output(DUMMY_DELL_SONIC_VERSION_TEXT)

    assert detection is not None
    assert detection.os_family == OSFamily.SONIC
    assert detection.platform == "Dell SONiC"
    assert detection.metadata["os_version"] == "4.1.0-Enterprise"
    assert detection.metadata["device_model"] == "DellEMC-S5248F-ON"


def test_parse_dell_sonic_version_output_rejects_non_dell():
    assert parse_dell_sonic_version_output(DUMMY_CISCO_NXOS_VERSION_TEXT) is None


def test_detect_network_os_arista_first(conn_mock):
    conn_mock.run_command.return_value = CommandArtifact(
        command=ARISTA_VERSION_CMD,
        stdout=DUMMY_ARISTA_VERSION_MINIMAL_JSON,
        stderr="",
        exit_code=0,
    )

    detection = detect_network_os(conn_mock)

    assert detection is not None
    assert detection.os_family == OSFamily.EOS
    assert detection.metadata["os_version"] == DUMMY_ARISTA_VERSION_MINIMAL["version"]
    conn_mock.run_command.assert_called_once_with(ARISTA_VERSION_CMD, timeout=30)


def test_detect_network_os_falls_back_to_dell(conn_mock):
    conn_mock.run_command.side_effect = [
        DUMMY_ARISTA_VERSION_CMD_FAILED,
        DUMMY_DELL_VERSION_CMD_MINIMAL_OK,
    ]

    detection = detect_network_os(conn_mock)

    assert detection is not None
    assert detection.os_family == OSFamily.SONIC
    assert detection.metadata["os_version"] == "4.0.0"
    assert conn_mock.run_command.call_count == 2


def test_check_os_family_detects_arista_eos(system_info, conn_mock):
    manager = InBandConnectionManager(system_info=system_info)
    manager.connection = conn_mock
    conn_mock.run_command.side_effect = [
        DUMMY_UNAME_FAILED,
        DUMMY_ARISTA_VERSION_CMD_OK,
    ]

    manager._check_os_family()

    assert system_info.os_family == OSFamily.EOS
    assert system_info.platform == "Arista EOS"
    assert system_info.metadata["os_version"] == DUMMY_ARISTA_VERSION["version"]
    assert system_info.metadata["device_model"] == DUMMY_ARISTA_VERSION["modelName"]
    assert not any(
        event.description == "Unable to determine SUT OS" for event in manager.result.events
    )


def test_check_os_family_detects_dell_sonic(system_info, conn_mock):
    system_info.os_family = OSFamily.UNKNOWN
    manager = InBandConnectionManager(system_info=system_info)
    manager.connection = conn_mock
    conn_mock.run_command.side_effect = [
        DUMMY_UNAME_FAILED,
        DUMMY_ARISTA_VERSION_CMD_FAILED,
        DUMMY_DELL_VERSION_CMD_OK,
    ]

    manager._check_os_family()

    assert system_info.os_family == OSFamily.SONIC
    assert system_info.platform == "Dell SONiC"
    assert system_info.metadata["os_version"] == "4.1.0-Enterprise"
    assert system_info.metadata["device_model"] == "DellEMC-S5248F-ON"
    assert not any(
        event.description == "Unable to determine SUT OS" for event in manager.result.events
    )


def test_check_os_family_still_warns_when_unknown(system_info, conn_mock):
    system_info.os_family = OSFamily.UNKNOWN
    manager = InBandConnectionManager(system_info=system_info)
    manager.connection = conn_mock
    conn_mock.run_command.side_effect = [
        DUMMY_UNAME_FAILED,
        DUMMY_ARISTA_VERSION_CMD_FAILED,
        DUMMY_DELL_VERSION_CMD_NON_DELL,
    ]

    manager._check_os_family()

    assert system_info.os_family == OSFamily.UNKNOWN
    assert any(
        event.description == "Unable to determine SUT OS" and event.category == "UNKNOWN"
        for event in manager.result.events
    )


def test_check_os_family_linux_skips_network_probes(system_info, conn_mock):
    manager = InBandConnectionManager(system_info=system_info)
    manager.connection = conn_mock
    conn_mock.run_command.return_value = DUMMY_UNAME_LINUX

    manager._check_os_family()

    assert system_info.os_family == OSFamily.LINUX
    conn_mock.run_command.assert_called_once_with("uname -s")
