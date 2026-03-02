###############################################################################
#
# MIT License
#
# Copyright (c) 2025 Advanced Micro Devices, Inc.
#
###############################################################################
from unittest.mock import MagicMock

import pytest

from nodescraper.enums.executionstatus import ExecutionStatus
from nodescraper.enums.systeminteraction import SystemInteractionLevel
from nodescraper.models.systeminfo import OSFamily
from nodescraper.plugins.inband.niccli.niccli_collector import NicCliCollector
from nodescraper.plugins.inband.niccli.niccli_data import (
    BroadcomNicDevice,
    BroadcomNicQos,
    NicCliDataModel,
    PensandoNicCard,
)


@pytest.fixture
def collector(system_info, conn_mock):
    return NicCliCollector(
        system_info=system_info,
        system_interaction_level=SystemInteractionLevel.PASSIVE,
        connection=conn_mock,
    )


NICCLI_LISTDEV_OUTPUT = """1) Broadcom BCM57608 1x400G QSFP-DD PCIe Ethernet NIC (Adp#1 Port#1)
    Device Interface                          : abcd1p1
    MAC Address                               : 81:82:83:84:85:88
    PCI Address                               : 0000:22:00.0
"""

NICCLI_QOS_OUTPUT = """IEEE 8021QAZ ETS Configuration TLV:
         PRIO_MAP: 0:0 1:0 2:0 3:1 4:0 5:0 6:0 7:2
         TC Bandwidth: 50% 50% 0%
         TSA_MAP: 0:ets 1:ets 2:strict
IEEE 8021QAZ PFC TLV:
         PFC enabled: 3
IEEE 8021QAZ APP TLV:
         APP#0:
          Priority: 7
          Sel: 5
          DSCP: 48

         APP#1:
          Priority: 3
          Sel: 5
          DSCP: 26

         APP#2:
          Priority: 3
          Sel: 3
          UDP or DCCP: 4791

TC Rate Limit: 100% 100% 100% 0% 0% 0% 0% 0%
"""


def test_parse_niccli_listdev_device(collector):
    """Test parsing Broadcom NIC device from niccli --list_devices output."""
    devices = collector._parse_niccli_listdev(NICCLI_LISTDEV_OUTPUT)

    assert len(devices) == 1
    device1 = devices[0]
    assert device1.device_num == 1
    assert device1.model == "Broadcom BCM57608 1x400G QSFP-DD PCIe Ethernet NIC"
    assert device1.adapter_port == "Adp#1 Port#1"
    assert device1.interface_name == "abcd1p1"
    assert device1.mac_address == "81:82:83:84:85:88"
    assert device1.pci_address == "0000:22:00.0"


def test_parse_niccli_listdev_empty_output(collector):
    """Test parsing empty niccli --list_devices output."""
    devices = collector._parse_niccli_listdev("")
    assert len(devices) == 0


def test_parse_niccli_listdev_malformed_output(collector):
    """Test parsing malformed niccli --list_devices output gracefully."""
    malformed = """some random text
not a valid device line
123 invalid format
"""
    devices = collector._parse_niccli_listdev(malformed)
    assert isinstance(devices, list)


def test_parse_niccli_qos_complete(collector):
    """Test parsing complete Broadcom NIC QoS output with all fields."""
    qos = collector._parse_niccli_qos(1, NICCLI_QOS_OUTPUT)

    assert qos.device_num == 1
    assert qos.raw_output == NICCLI_QOS_OUTPUT
    assert len(qos.prio_map) == 8
    assert qos.prio_map[0] == 0
    assert qos.prio_map[3] == 1
    assert qos.prio_map[7] == 2
    assert len(qos.tc_bandwidth) == 3
    assert qos.tc_bandwidth[0] == 50
    assert qos.tc_bandwidth[1] == 50
    assert qos.tc_bandwidth[2] == 0
    assert len(qos.tsa_map) == 3
    assert qos.tsa_map[0] == "ets"
    assert qos.tsa_map[2] == "strict"
    assert qos.pfc_enabled == 3
    assert len(qos.app_entries) == 3
    assert qos.app_entries[0].priority == 7
    assert qos.app_entries[0].sel == 5
    assert qos.app_entries[0].dscp == 48
    assert qos.app_entries[2].protocol == "UDP or DCCP"
    assert qos.app_entries[2].port == 4791
    assert len(qos.tc_rate_limit) == 8
    assert qos.tc_rate_limit[0] == 100


def test_parse_niccli_qos_empty_output(collector):
    """Test parsing empty QoS output."""
    qos = collector._parse_niccli_qos(1, "")
    assert qos.device_num == 1
    assert qos.raw_output == ""
    assert len(qos.prio_map) == 0
    assert len(qos.tc_bandwidth) == 0
    assert len(qos.tsa_map) == 0
    assert qos.pfc_enabled is None
    assert len(qos.app_entries) == 0
    assert len(qos.tc_rate_limit) == 0


def test_parse_niccli_qos_multiple_app_protocols(collector):
    """Test parsing QoS with APP entries having different protocols."""
    qos_multi_protocol = """IEEE 8021QAZ ETS Configuration TLV:
         PRIO_MAP: 0:0
         TC Bandwidth: 100%
         TSA_MAP: 0:ets
IEEE 8021QAZ PFC TLV:
         PFC enabled: 0
IEEE 8021QAZ APP TLV:
         APP#0:
          Priority: 5
          Sel: 3
          TCP: 8080

         APP#1:
          Priority: 6
          Sel: 3
          UDP: 9000

TC Rate Limit: 100%
"""
    qos = collector._parse_niccli_qos(3, qos_multi_protocol)
    assert len(qos.app_entries) == 2
    assert qos.app_entries[0].priority == 5
    assert qos.app_entries[0].sel == 3
    assert qos.app_entries[0].protocol == "TCP"
    assert qos.app_entries[0].port == 8080
    assert qos.app_entries[1].priority == 6
    assert qos.app_entries[1].protocol == "UDP"
    assert qos.app_entries[1].port == 9000


def test_parse_niccli_qos_malformed_values(collector):
    """Test parsing QoS output with malformed values gracefully."""
    malformed = """IEEE 8021QAZ ETS Configuration TLV:
         PRIO_MAP: 0:invalid 1:1 bad:data
         TC Bandwidth: 50% invalid 50%
         TSA_MAP: 0:ets bad:value 1:strict
IEEE 8021QAZ PFC TLV:
         PFC enabled: not_a_number
TC Rate Limit: 100% bad% 100%
"""
    qos = collector._parse_niccli_qos(1, malformed)
    assert qos.device_num == 1
    assert 1 in qos.prio_map
    assert qos.prio_map[1] == 1
    assert 50 in qos.tc_bandwidth
    assert qos.tsa_map.get(0) == "ets"
    assert qos.tsa_map.get(1) == "strict"
    assert qos.pfc_enabled is None


def test_niccli_data_model_with_broadcom_nic(collector):
    """Test creating NicCliDataModel with Broadcom NIC data."""
    device = BroadcomNicDevice(
        device_num=1,
        model="Broadcom BCM57608 1x400G QSFP-DD PCIe Ethernet NIC",
        adapter_port="Adp#1 Port#1",
        interface_name="benic1p1",
        mac_address="8C:84:74:37:C3:70",
        pci_address="0000:06:00.0",
    )
    qos = BroadcomNicQos(
        device_num=1,
        raw_output="test output",
        prio_map={0: 0, 1: 1},
        tc_bandwidth=[50, 50],
        tsa_map={0: "ets", 1: "strict"},
        pfc_enabled=3,
        tc_rate_limit=[100, 100],
    )
    data = NicCliDataModel(
        broadcom_nic_devices=[device],
        broadcom_nic_qos={1: qos},
    )
    assert len(data.broadcom_nic_devices) == 1
    assert len(data.broadcom_nic_qos) == 1
    assert data.broadcom_nic_devices[0].device_num == 1
    assert data.broadcom_nic_devices[0].interface_name == "benic1p1"
    assert data.broadcom_nic_qos[1].device_num == 1
    assert data.broadcom_nic_qos[1].pfc_enabled == 3


def test_niccli_data_model_with_pensando_nic(collector):
    """Test creating NicCliDataModel with Pensando NIC data."""
    card1 = PensandoNicCard(
        id="42424650-4c32-3533-3330-323934000000",
        pcie_bdf="0000:06:00.0",
        asic="salina",
        fw_partition="A",
        serial_number="FPL25330294",
    )
    card2 = PensandoNicCard(
        id="42424650-4c32-3533-3731-304535000000",
        pcie_bdf="0000:16:00.0",
        asic="salina",
        fw_partition="A",
        serial_number="FPL253710E5",
    )
    data = NicCliDataModel(
        pensando_nic_cards=[card1, card2],
    )
    assert len(data.pensando_nic_cards) == 2
    assert data.pensando_nic_cards[0].id == "42424650-4c32-3533-3330-323934000000"
    assert data.pensando_nic_cards[0].pcie_bdf == "0000:06:00.0"
    assert data.pensando_nic_cards[0].asic == "salina"
    assert data.pensando_nic_cards[1].serial_number == "FPL253710E5"


def test_collect_data_success(collector, conn_mock):
    """Test successful collection of niccli/nicctl data."""
    collector.system_info.os_family = OSFamily.LINUX

    def run_sut_cmd_side_effect(cmd, **kwargs):
        if "niccli" in cmd and ("--list" in cmd or "--list_devices" in cmd):
            return MagicMock(exit_code=0, stdout=NICCLI_LISTDEV_OUTPUT, command=cmd)
        if "nicctl show card --json" in cmd:
            return MagicMock(
                exit_code=0,
                stdout='[{"id": "1111111-4c32-3533-3330-12345000000"}]',
                command=cmd,
            )
        if "nicctl" in cmd or "niccli" in cmd:
            return MagicMock(exit_code=0, stdout="", command=cmd)
        return MagicMock(exit_code=1, stdout="", command=cmd)

    collector._run_sut_cmd = MagicMock(side_effect=run_sut_cmd_side_effect)

    result, data = collector.collect_data()

    assert result.status == ExecutionStatus.OK
    assert data is not None
    assert isinstance(data, NicCliDataModel)
    assert len(data.results) >= 1
